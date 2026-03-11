from __future__ import annotations

import asyncio
from asyncio import Lock
from itertools import count

import websockets
from typing_extensions import Any, cast
from websockets.asyncio.client import ClientConnection
from websockets.asyncio.server import Server, ServerConnection
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response

from melobot.log import LogLevel, logger
from melobot.utils import truncate


class WSClientImpl:
    def __init__(
        self,
        name: str,
        url: str,
        req_headers: dict[str, str] | None = None,
        max_retry: int = -1,
        retry_delay: float = 4.0,
    ) -> None:
        self.name = f"[{name}]"
        self.url = url
        self.conn: ClientConnection
        self.max_retry: int = max_retry
        self.retry_delay: float = retry_delay if retry_delay > 0 else 0.5

        self._req_headers = req_headers
        self._tasks: list[asyncio.Task] = []
        self._opened = asyncio.Event()
        self._lock = Lock()
        self._restarting = asyncio.Event()

    async def _input_loop(self) -> None:
        while True:
            try:
                await self._opened.wait()
                raw = await self.conn.recv()
                logger.generic_lazy(
                    f"{self.name} 收到数据：\n%s",
                    lambda: truncate(cast(Any, raw)),
                    level=LogLevel.DEBUG,
                )
                await self._on_received(raw)
            except asyncio.CancelledError:
                raise
            except ConnectionClosed:
                if self._opened.is_set():
                    self._restarting.set()
                    asyncio.create_task(self._stop())
                break
            except Exception:
                local_vars = locals()
                if (val := local_vars.pop("raw", None)) is not None:
                    local_vars["raw"] = truncate(val)
                logger.generic_exc(f"{self.name} 接收数据时抛出异常", obj=local_vars)

    async def _output_loop(self) -> None:
        while True:
            try:
                await self._opened.wait()
                out = await self._on_get_output()
                if out is None:
                    continue
                logger.generic_lazy(
                    f"{self.name} 发送数据：\n%s",
                    lambda: truncate(cast(Any, out)),
                    level=LogLevel.DEBUG,
                )
                await self.conn.send(out)
                await self._on_sent(out)
            except asyncio.CancelledError:
                raise
            except Exception:
                local_vars = locals()
                if (val := local_vars.pop("out", None)) is not None:
                    local_vars["out"] = truncate(val)
                logger.generic_exc(f"{self.name} 发送数据时抛出异常", obj=local_vars)

    async def _start(self) -> None:
        if self._opened.is_set():
            return

        async with self._lock:
            if self._opened.is_set():
                return

            retry_iter = count(0) if self.max_retry < 0 else range(self.max_retry + 1)
            for _ in retry_iter:
                try:
                    self.conn = await websockets.connect(
                        self.url, additional_headers=self._req_headers
                    )
                    break
                except asyncio.CancelledError:
                    raise
                except BaseException as e:
                    logger.warning(
                        f"{self.name} 与 ws 服务端建立连接失败，{self.retry_delay}s 后重试。错误：{e}"
                    )
                await asyncio.sleep(self.retry_delay)

            else:
                raise RuntimeError(f"{self.name} 重试过多，已放弃与 ws 服务端建立连接")

            self._tasks.append(asyncio.create_task(self._input_loop()))
            self._tasks.append(asyncio.create_task(self._output_loop()))
            self._opened.set()
            logger.info(f"{self.name} 与 ws 服务端 ({self.url}) 建立连接成功")

            if self._restarting.is_set():
                self._restarting.clear()
                await self._on_relinked()

    async def _stop(self) -> None:
        if not self._opened.is_set():
            return

        async with self._lock:
            if not self._opened.is_set():
                return

            self.conn.close_timeout = 2
            self._opened.clear()
            await self.conn.close()
            await self.conn.wait_closed()

            for t in self._tasks:
                t.cancel()
            if len(self._tasks):
                await asyncio.wait(self._tasks)
            self._tasks.clear()
            logger.info(f"{self.name} 与 ws 服务端断开了连接")
            if self._restarting.is_set():
                logger.info(f"{self.name} {self.retry_delay}s 后尝试重连 ws 服务端...")
                await asyncio.sleep(self.retry_delay)
                asyncio.create_task(self._start())

    async def _on_received(self, raw: str | bytes) -> None:
        pass

    async def _on_get_output(self) -> str | bytes | None:
        # 子类不实现则没有输出功能，这样设置避免自旋
        logger.warning(f"{self.name} 未实现输出功能，无法发送任何数据")
        await asyncio.get_running_loop().create_future()
        return None

    async def _on_sent(self, out: str | bytes) -> None:
        pass

    async def _on_relinked(self) -> None:
        pass


class WSServerImpl:
    def __init__(self, name: str, host: str, port: int) -> None:
        self.name = f"[{name}]"
        self.host = host
        self.port = port
        self.conn: ServerConnection
        self.server: Server

        self._tasks: list[asyncio.Task] = []
        self._opened = asyncio.Event()
        self._linked = asyncio.Event()
        self._lock = asyncio.Lock()
        self._restarting = asyncio.Event()

    async def _input_loop(self, ws: ServerConnection) -> None:
        if not self.server.is_serving():
            return
        self.conn = ws
        self._opened.set()
        self._linked.set()
        logger.info(f"{self.name} 已与 ws 客户端建立了连接")

        if self._restarting.is_set():
            self._restarting.clear()
            await self._on_relinked()

        while True:
            try:
                raw = await self.conn.recv()
                logger.generic_lazy(
                    f"{self.name} 收到数据：\n%s",
                    lambda: truncate(cast(Any, raw)),
                    level=LogLevel.DEBUG,
                )
                await self._on_received(raw)
            except asyncio.CancelledError:
                raise
            except ConnectionClosed:
                logger.info(f"{self.name} 与 ws 客户端断开了连接，等待新的连接请求...")
                self._linked.clear()
                self._restarting.set()
                await self._on_unlinked(ws)
                break
            except Exception:
                local_vars = locals()
                if (val := local_vars.pop("raw", None)) is not None:
                    local_vars["raw"] = truncate(val)
                logger.generic_exc(f"{self.name} 接收数据时抛出异常", obj=local_vars)

    async def _output_loop(self) -> None:
        while True:
            try:
                await self._linked.wait()
                out = await self._on_get_output()
                if out is None:
                    continue
                logger.generic_lazy(
                    f"{self.name} 发送数据：\n%s",
                    lambda: truncate(cast(Any, out)),
                    level=LogLevel.DEBUG,
                )
                await self.conn.send(out)
                await self._on_sent(out)
            except asyncio.CancelledError:
                raise
            except Exception:
                local_vars = locals()
                if (val := local_vars.pop("out", None)) is not None:
                    local_vars["out"] = truncate(val)
                logger.generic_exc(f"{self.name} 发送数据时抛出异常", obj=local_vars)

    async def _start(self) -> None:
        if self._opened.is_set():
            return

        async with self._lock:
            if self._opened.is_set():
                return

            self.server = await websockets.serve(
                self._input_loop,
                self.host,
                self.port,
                process_request=self._on_req,
                ping_interval=3,
                ping_timeout=2,
            )
            logger.info(f"{self.name} ws 服务端已启动 (ws://{self.host}:{self.port})")
            self._tasks.append(asyncio.create_task(self._output_loop()))
            logger.info(f"{self.name} 等待 ws 客户端连接中...")
            await self._opened.wait()

    async def _stop(self) -> None:
        if not self._opened.is_set():
            return

        async with self._lock:
            if not self._opened.is_set():
                return

            self._opened.clear()
            self.server.close()  # type: ignore[func-returns-value]
            await self.server.wait_closed()

            for t in self._tasks:
                t.cancel()
            if len(self._tasks):
                await asyncio.wait(self._tasks)
            self._tasks.clear()
            logger.info(f"{self.name} 已停止工作")

    async def _on_req(self, conn: ServerConnection, req: Request) -> Response | None:
        pass

    async def _on_received(self, raw: str | bytes) -> None:
        pass

    async def _on_get_output(self) -> str | bytes | None:
        # 子类不实现则没有输出功能，这样设置避免自旋
        logger.warning(f"{self.name} 未实现输出功能，无法发送任何数据")
        await asyncio.get_running_loop().create_future()
        return None

    async def _on_sent(self, out: str | bytes) -> None:
        pass

    async def _on_unlinked(self, ws: ServerConnection) -> None:
        pass

    async def _on_relinked(self) -> None:
        pass
