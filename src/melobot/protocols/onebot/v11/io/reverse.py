from __future__ import annotations

import asyncio
import http
import json
import time
from asyncio import Future

import websockets
from typing_extensions import Any, cast
from websockets import ConnectionClosed
from websockets.asyncio.server import Server, ServerConnection
from websockets.http11 import Request, Response

from melobot.io import SourceLifeSpan
from melobot.log import LogLevel, log_exc, logger
from melobot.utils import truncate

from .base import BaseIOSource
from .packet import EchoPacket, InPacket, OutPacket


class ReverseImpl:
    def __init__(self, name: str, host: str, port: int) -> None:
        self.name = f"[{name}]"
        self.host = host
        self.port = port
        self.conn: ServerConnection
        self.server: Server

        self._tasks: list[asyncio.Task] = []
        self._opened = asyncio.Event()
        self._lock = asyncio.Lock()
        self._restarting = asyncio.Event()

    async def _input_loop(self, ws: ServerConnection) -> None:
        self.conn = ws
        self._opened.set()
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
                self._opened.clear()
                self._restarting.set()
                await self._on_unlinked(ws)
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
        await asyncio.get_running_loop().create_future()
        return None

    async def _on_sent(self, out: str | bytes) -> None:
        pass

    async def _on_unlinked(self, ws: ServerConnection) -> None:
        pass

    async def _on_relinked(self) -> None:
        pass


class ReverseIO(ReverseImpl, BaseIOSource):
    INSTANCE_COUNT = 0

    def __new__(cls, *args: Any, **kwargs: Any) -> ReverseIO:
        o = super().__new__(cls)
        cls.INSTANCE_COUNT += 1
        return o

    def __init__(
        self,
        host: str,
        port: int,
        cd_time: float = 0,
        access_token: str | None = None,
        name: str | None = None,
    ) -> None:
        BaseIOSource.__init__(self, cd_time=cd_time)
        ReverseImpl.__init__(
            self,
            name=f"OB11 反向 #{self.INSTANCE_COUNT}" if name is None else name,
            host=host,
            port=port,
        )
        self._hook_bus.set_tag(self.name)
        self.access_token = access_token

        self._req_lock = asyncio.Lock()
        self._conn_requested = False
        self._in_buf: asyncio.Queue[InPacket] = asyncio.Queue()
        self._out_buf: asyncio.Queue[OutPacket] = asyncio.Queue()
        self._echo_table: dict[str, tuple[str, Future[EchoPacket]]] = {}
        self._pre_send_time = time.time_ns()

    async def _on_req(self, conn: ServerConnection, req: Request) -> Response | None:
        _headers = dict(req.headers)
        reconn_refused = "Already accepted the unique connection\n"
        auth_failed = "Authorization failed\n"
        if self._conn_requested:
            return conn.respond(http.HTTPStatus.FORBIDDEN, reconn_refused)

        async with self._req_lock:
            if self._conn_requested:
                return conn.respond(http.HTTPStatus.FORBIDDEN, reconn_refused)
            if (
                self.access_token is not None
                and _headers.get("authorization") != f"Bearer {self.access_token}"
                and _headers.get("Authorization") != f"Bearer {self.access_token}"
            ):
                logger.warning(f"{self.name} ws 客户端请求的 access_token 不匹配，拒绝连接")
                return conn.respond(http.HTTPStatus.FORBIDDEN, auth_failed)

            self._conn_requested = True
            return None

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

    async def _on_unlinked(self, ws: ServerConnection) -> None:
        self._conn_requested = False

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
