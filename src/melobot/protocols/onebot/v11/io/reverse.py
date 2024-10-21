# pylint: disable=duplicate-code
import asyncio
import http
import json
import time
from asyncio import Future
from typing import Callable

import websockets
import websockets.server
from websockets import ConnectionClosed

from melobot.log import LogLevel

from .base import BaseIO
from .packet import EchoPacket, InPacket, OutPacket


class ReverseWebSocketIO(BaseIO):
    def __init__(
        self, host: str, port: int, cd_time: float = 0.2, access_token: str | None = None
    ) -> None:
        super().__init__(cd_time)
        self.host = host
        self.port = port
        self.conn: websockets.server.WebSocketServerProtocol
        self.server: websockets.server.WebSocketServer
        self.access_token = access_token

        self._tasks: list[asyncio.Task] = []
        self._in_buf: asyncio.Queue[InPacket] = asyncio.Queue()
        self._out_buf: asyncio.Queue[OutPacket] = asyncio.Queue()
        self._echo_table: dict[str, tuple[str, Future[EchoPacket]]] = {}
        self._opened = asyncio.Event()
        self._pre_send_time = time.time_ns()
        self._conn_requested = False
        self._request_lock = asyncio.Lock()

    async def _req_check(
        self, _: str, headers: websockets.HeadersLike
    ) -> tuple[http.HTTPStatus, websockets.HeadersLike, bytes] | None:
        _headers = dict(headers)

        resp_403: Callable[[str], tuple[http.HTTPStatus, list, bytes]] = lambda x: (
            http.HTTPStatus.FORBIDDEN,
            [],
            x.encode(),
        )
        reconn_refused = "Already accepted the unique connection\n"
        auth_failed = "Authorization failed\n"

        if self._conn_requested:
            return resp_403(reconn_refused)

        async with self._request_lock:
            if self._conn_requested:
                return resp_403(reconn_refused)

            if (
                self.access_token is not None
                and _headers.get("Authorization") != f"Bearer {self.access_token}"
            ):
                self.logger.warning("OneBot 实现端的 access_token 不匹配，拒绝连接")
                return resp_403(auth_failed)

            self._conn_requested = True
            return None

    async def _input_loop(self, ws: websockets.server.WebSocketServerProtocol) -> None:
        # pylint: disable=duplicate-code
        self.conn = ws
        self._opened.set()
        self.logger.info("OneBot v11 反向 WebSocket IO 源与实现端建立了连接")

        while True:
            try:
                raw_str = await self.conn.recv()
                self.logger.generic_obj(
                    "收到上报，未格式化的字符串", raw_str, level=LogLevel.DEBUG
                )
                if raw_str == "":
                    continue
                raw = json.loads(raw_str)

                if "post_type" in raw:
                    await self._in_buf.put(InPacket(time=raw["time"], data=raw))
                    continue

                echo_id = raw.get("echo")
                if echo_id in (None, ""):
                    continue

                action_type, fut = self._echo_table.pop(echo_id)
                fut.set_result(
                    EchoPacket(
                        time=int(time.time()),
                        data=raw,
                        ok=raw["status"] == "ok",
                        status=raw["retcode"],
                        action_type=action_type,
                    )
                )
            except ConnectionClosed:
                self.logger.warning("OneBot v11 正向 WebSocket IO 源的 ws 连接已关闭")
                break
            except Exception:
                self.logger.exception("OneBot v11 反向 WebSocket IO 源输入异常")
                self.logger.generic_obj("异常点局部变量", locals(), level=LogLevel.ERROR)
                self.logger.generic_obj("异常点的上报数据", raw, level=LogLevel.ERROR)

    async def _output_loop(self) -> None:
        while True:
            try:
                out_packet = await self._out_buf.get()
                wait_time = self.cd_time - ((time.time_ns() - self._pre_send_time) / 1e9)
                await asyncio.sleep(wait_time)
                await self.conn.send(out_packet.data)
                self._pre_send_time = time.time_ns()
            except Exception:
                self.logger.exception("OneBot v11 反向 WebSocket IO 源输出异常")
                self.logger.generic_obj("异常点局部变量", locals(), level=LogLevel.ERROR)
                self.logger.generic_obj(
                    "异常点的发送数据", out_packet.data, level=LogLevel.ERROR
                )

    async def open(self) -> None:
        self.server = await websockets.serve(
            self._input_loop, self.host, self.port, process_request=self._req_check
        )
        self._tasks.append(asyncio.create_task(self._output_loop()))
        self.logger.info("OneBot v11 反向 WebSocket IO 源启动了服务，等待连接中")
        await self._opened.wait()

    def opened(self) -> bool:
        return self._opened.is_set()

    async def close(self) -> None:
        if self.opened():
            await self.server.close()  # type: ignore[func-returns-value]
            await self.server.wait_closed()
            for t in self._tasks:
                t.cancel()

            self._opened.clear()
            self.logger.info("OneBot v11 反向 WebSocket IO 源已停止运行")

    async def input(self) -> InPacket:
        return await self._in_buf.get()

    async def output(self, packet: OutPacket) -> EchoPacket:
        await self._out_buf.put(packet)
        if packet.echo_id is None:
            return EchoPacket(noecho=True)

        fut: Future[EchoPacket] = Future()
        self._echo_table[packet.echo_id] = (packet.action_type, fut)
        return await fut
