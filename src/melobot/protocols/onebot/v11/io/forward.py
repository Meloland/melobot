from __future__ import annotations

import asyncio
import json
import time
from asyncio import Future, Lock
from itertools import count

import websockets
from typing_extensions import Any, cast
from websockets.asyncio.client import ClientConnection
from websockets.exceptions import ConnectionClosed

from melobot.exceptions import SourceError
from melobot.io import SourceLifeSpan
from melobot.log import LogLevel, log_exc, logger
from melobot.utils import truncate

from .base import BaseIOSource
from .packet import EchoPacket, InPacket, OutPacket


class ForwardImpl:
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
        self._out_buf: asyncio.Queue[OutPacket] = asyncio.Queue()
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
            except Exception as e:
                local_vars = locals()
                if (val := local_vars.pop("raw", None)) is not None:
                    local_vars["raw"] = truncate(val)
                log_exc(e, msg=f"{self.name} 接收数据时抛出异常", obj=local_vars)

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
            except Exception as e:
                local_vars = locals()
                if (val := local_vars.pop("out", None)) is not None:
                    local_vars["out"] = truncate(val)
                log_exc(e, msg=f"{self.name} 发送数据时抛出异常", obj=local_vars)

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
                raise SourceError(f"{self.name} 重试过多，已放弃与 ws 服务端建立连接")

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
        await asyncio.get_running_loop().create_future()
        return None

    async def _on_sent(self, out: str | bytes) -> None:
        pass

    async def _on_relinked(self) -> None:
        pass


class ForwardIO(ForwardImpl, BaseIOSource):
    INSTANCE_COUNT = 0

    def __new__(cls, *args: Any, **kwargs: Any) -> ForwardIO:
        o = super().__new__(cls)
        cls.INSTANCE_COUNT += 1
        return o

    def __init__(
        self,
        url: str,
        max_retry: int = -1,
        retry_delay: float = 4.0,
        cd_time: float = 0,
        access_token: str | None = None,
        name: str | None = None,
    ) -> None:
        BaseIOSource.__init__(self, cd_time=cd_time)
        ForwardImpl.__init__(
            self,
            name=f"OB11 正向 #{ForwardIO.INSTANCE_COUNT}" if name is None else name,
            url=url,
            req_headers=(
                None if access_token is None else {"Authorization": f"Bearer {access_token}"}
            ),
            max_retry=max_retry,
            retry_delay=retry_delay,
        )
        self._hook_bus.set_tag(self.name)

        self._in_buf: asyncio.Queue[InPacket] = asyncio.Queue()
        self._out_buf: asyncio.Queue[OutPacket] = asyncio.Queue()
        self._pre_send_time = time.time_ns()
        self._echo_table: dict[str, tuple[str, Future[EchoPacket]]] = {}

    async def _on_received(self, raw: str | bytes) -> None:
        if raw == "":
            return

        raw_dic = json.loads(raw)
        if "post_type" in raw_dic:
            await self._in_buf.put(InPacket(time=raw_dic["time"], data=raw_dic))
            return

        echo_id = raw_dic.get("echo")
        if echo_id in (None, ""):
            return
        action_type, fut = self._echo_table.pop(echo_id)
        fut.set_result(
            EchoPacket(
                time=int(time.time()),
                data=raw_dic,
                ok=raw_dic["status"] == "ok",
                status=raw_dic["retcode"],
                action_type=action_type,
            )
        )

    async def _on_get_output(self) -> str | bytes:
        out_packet = await self._out_buf.get()
        wait_time = self.cd_time - ((time.time_ns() - self._pre_send_time) / 1e9)
        await asyncio.sleep(wait_time)
        return out_packet.data

    async def _on_sent(self, out: str | bytes) -> None:
        self._pre_send_time = time.time_ns()

    async def _on_relinked(self) -> None:
        await self._hook_bus.emit(SourceLifeSpan.RESTARTED, False)

    async def open(self) -> None:
        await self._start()

    def opened(self) -> bool:
        return self._opened.is_set()

    async def close(self) -> None:
        await self._stop()

    async def input(self) -> InPacket:
        return await self._in_buf.get()

    async def output(self, packet: OutPacket) -> EchoPacket:
        await self._out_buf.put(packet)
        if packet.echo_id is None:
            return EchoPacket(noecho=True)

        fut: Future[EchoPacket] = asyncio.get_running_loop().create_future()
        self._echo_table[packet.echo_id] = (packet.action_type, fut)
        return await fut
