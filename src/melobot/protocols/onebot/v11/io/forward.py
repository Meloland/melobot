import asyncio
import json
import time
from asyncio import Future, Lock
from itertools import count

import websockets
from websockets.asyncio.client import ClientConnection
from websockets.exceptions import ConnectionClosed

from melobot.exceptions import SourceError
from melobot.io import SourceLifeSpan
from melobot.log import LogLevel

from .base import BaseIOSource
from .packet import EchoPacket, InPacket, OutPacket


class ForwardWebSocketIO(BaseIOSource):
    def __init__(
        self,
        url: str,
        max_retry: int = -1,
        retry_delay: float = 4.0,
        cd_time: float = 0,
        access_token: str | None = None,
    ) -> None:
        super().__init__(cd_time)
        self.url = url
        self.conn: ClientConnection
        self.access_token = access_token
        self.max_retry: int = max_retry
        self.retry_delay: float = retry_delay if retry_delay > 0 else 0.5

        self._in_buf: asyncio.Queue[InPacket] = asyncio.Queue()
        self._out_buf: asyncio.Queue[OutPacket] = asyncio.Queue()
        self._pre_send_time = time.time_ns()
        self._echo_table: dict[str, tuple[str, Future[EchoPacket]]] = {}

        self._tasks: list[asyncio.Task] = []
        self._opened = asyncio.Event()
        self._lock = Lock()
        self._restart_flag = asyncio.Event()

    async def _input_loop(self) -> None:
        while True:
            try:
                await self._opened.wait()

                raw_str = await self.conn.recv()
                self.logger.generic_obj("收到上报，未格式化的字符串", raw_str, level=LogLevel.DEBUG)
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
                break

            except ConnectionClosed:
                if self.opened():
                    self._restart_flag.set()
                    asyncio.create_task(self.close())
                break

            except Exception:
                self.logger.exception("OneBot v11 正向 WebSocket IO 源输入异常")
                self.logger.generic_obj("异常点局部变量", locals(), level=LogLevel.ERROR)

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
                break

            except Exception:
                self.logger.exception("OneBot v11 正向 WebSocket IO 源输出异常")
                self.logger.generic_obj("异常点局部变量", locals(), level=LogLevel.ERROR)

    async def open(self) -> None:
        if self.opened():
            return

        async with self._lock:
            if self.opened():
                return

            headers: dict | None = None
            if self.access_token is not None:
                headers = {"Authorization": f"Bearer {self.access_token}"}

            retry_iter = count(0) if self.max_retry < 0 else range(self.max_retry + 1)
            for _ in retry_iter:
                try:
                    self.conn = await websockets.connect(self.url, additional_headers=headers)
                    break

                except asyncio.CancelledError:
                    raise

                except BaseException as e:
                    self.logger.warning(f"连接建立失败，{self.retry_delay}s 后自动重试。错误：{e}")
                    if "403" in str(e):
                        self.logger.warning("403 错误可能是 access_token 未配置或无效")

                await asyncio.sleep(self.retry_delay)

            else:
                raise SourceError("OneBot v11 正向 WebSocket IO 源重试已达最大次数，已放弃建立连接")

            self._tasks.append(asyncio.create_task(self._input_loop()))
            self._tasks.append(asyncio.create_task(self._output_loop()))
            self._opened.set()
            self.logger.info("OneBot v11 正向 WebSocket IO 源与实现端建立了连接")

            if self._restart_flag.is_set():
                self._restart_flag.clear()
                await self._hook_bus.emit(SourceLifeSpan.RESTARTED, False)

    def opened(self) -> bool:
        return self._opened.is_set()

    async def close(self) -> None:
        if not self.opened():
            return

        async with self._lock:
            if not self.opened():
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
            self.logger.info("OneBot v11 正向 WebSocket IO 源已断开连接")

            if self._restart_flag.is_set():
                asyncio.create_task(self.open())

    async def input(self) -> InPacket:
        return await self._in_buf.get()

    async def output(self, packet: OutPacket) -> EchoPacket:
        await self._out_buf.put(packet)
        if packet.echo_id is None:
            return EchoPacket(noecho=True)

        fut: Future[EchoPacket] = asyncio.get_running_loop().create_future()
        self._echo_table[packet.echo_id] = (packet.action_type, fut)
        return await fut
