import asyncio
import http
import json
import time
from asyncio import Future

import websockets
from websockets import ConnectionClosed
from websockets.asyncio.server import Server, ServerConnection
from websockets.http11 import Request, Response

from melobot.io import SourceLifeSpan
from melobot.log import LogLevel, log_exc, logger

from .base import BaseIOSource
from .packet import EchoPacket, InPacket, OutPacket


class ReverseWebSocketIO(BaseIOSource):
    def __init__(
        self, host: str, port: int, cd_time: float = 0, access_token: str | None = None
    ) -> None:
        super().__init__(cd_time)
        self.host = host
        self.port = port
        self.conn: ServerConnection
        self.server: Server
        self.access_token = access_token

        self._in_buf: asyncio.Queue[InPacket] = asyncio.Queue()
        self._out_buf: asyncio.Queue[OutPacket] = asyncio.Queue()
        self._echo_table: dict[str, tuple[str, Future[EchoPacket]]] = {}
        self._pre_send_time = time.time_ns()

        self._tasks: list[asyncio.Task] = []
        self._opened = asyncio.Event()
        self._conn_requested = False
        self._req_lock = asyncio.Lock()
        self._lock = asyncio.Lock()
        self._restart_flag = asyncio.Event()

    async def _req_check(self, conn: ServerConnection, req: Request) -> Response | None:
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
                logger.warning("OneBot 实现端的 access_token 不匹配，拒绝连接")
                return conn.respond(http.HTTPStatus.FORBIDDEN, auth_failed)

            self._conn_requested = True
            return None

    async def _input_loop(self, ws: ServerConnection) -> None:
        self.conn = ws
        self._opened.set()
        logger.info("实现端与 OneBot v11 反向 WebSocket IO 源建立了连接")

        if self._restart_flag.is_set():
            self._restart_flag.clear()
            await self._hook_bus.emit(SourceLifeSpan.RESTARTED, False)

        while True:
            try:
                raw_str = await self.conn.recv()
                logger.generic_obj("收到上报，未格式化的字符串", raw_str, level=LogLevel.DEBUG)
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

            except asyncio.CancelledError:
                raise

            except ConnectionClosed:
                logger.info("实现端与 OneBot v11 反向 WebSocket IO 源已断连，等待连接中")
                self._opened.clear()
                self._restart_flag.set()
                self._conn_requested = False
                break

            except Exception as e:
                log_exc(e, "OneBot v11 反向 WebSocket IO 源输入异常", obj=locals())

    async def _output_loop(self) -> None:
        while True:
            try:
                await self._opened.wait()

                out_packet = await self._out_buf.get()
                wait_time = self.cd_time - ((time.time_ns() - self._pre_send_time) / 1e9)
                await asyncio.sleep(wait_time)
                await self.conn.send(out_packet.data)
                self._pre_send_time = time.time_ns()

            except asyncio.CancelledError:
                raise

            except Exception as e:
                log_exc(e, msg="OneBot v11 反向 WebSocket IO 源输出异常", obj=locals())

    async def open(self) -> None:
        if self.opened():
            return

        async with self._lock:
            if self.opened():
                return

            self.server = await websockets.serve(
                self._input_loop, self.host, self.port, process_request=self._req_check
            )
            self._tasks.append(asyncio.create_task(self._output_loop()))
            logger.info("OneBot v11 反向 WebSocket IO 源启动了服务，等待连接中")
            await self._opened.wait()

    def opened(self) -> bool:
        return self._opened.is_set()

    async def close(self) -> None:
        if not self.opened():
            return

        async with self._lock:
            if not self.opened():
                return

            self._opened.clear()
            self.server.close()  # type: ignore[func-returns-value]
            await self.server.wait_closed()

            for t in self._tasks:
                t.cancel()
            if len(self._tasks):
                await asyncio.wait(self._tasks)
            self._tasks.clear()
            logger.info("OneBot v11 反向 WebSocket IO 源的服务已停止运行")

    async def input(self) -> InPacket:
        return await self._in_buf.get()

    async def output(self, packet: OutPacket) -> EchoPacket:
        await self._out_buf.put(packet)
        if packet.echo_id is None:
            return EchoPacket(noecho=True)

        fut: Future[EchoPacket] = asyncio.get_running_loop().create_future()
        self._echo_table[packet.echo_id] = (packet.action_type, fut)
        return await fut
