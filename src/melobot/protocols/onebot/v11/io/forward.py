# pylint: disable=duplicate-code
import asyncio
import json
import time
from asyncio import Future
from itertools import count

import websockets
from websockets.exceptions import ConnectionClosed

from melobot.exceptions import IOError
from melobot.log import LogLevel

from .base import BaseIO
from .packet import EchoPacket, InPacket, OutPacket


class ForwardWebSocketIO(BaseIO):
    def __init__(
        self,
        url: str,
        max_retry: int = -1,
        retry_delay: float = 4.0,
        cd_time: float = 0.2,
        access_token: str | None = None,
    ) -> None:
        super().__init__(cd_time)
        self.url = url
        self.conn: websockets.client.WebSocketClientProtocol
        self.access_token = access_token
        self.max_retry: int = max_retry
        self.retry_delay: float = retry_delay if retry_delay > 0 else 0

        self._tasks: list[asyncio.Task] = []
        self._in_buf: asyncio.Queue[InPacket] = asyncio.Queue()
        self._out_buf: asyncio.Queue[OutPacket] = asyncio.Queue()
        self._echo_table: dict[str, tuple[str, Future[EchoPacket]]] = {}
        self._opened = False
        self._pre_send_time = time.time_ns()

    async def _input_loop(self) -> None:
        # pylint: disable=duplicate-code
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
                self.logger.exception("OneBot v11 正向 WebSocket IO 源输入异常")
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
                self.logger.exception("OneBot v11 正向 WebSocket IO 源输出异常")
                self.logger.generic_obj("异常点局部变量", locals(), level=LogLevel.ERROR)
                self.logger.generic_obj(
                    "异常点的发送数据", out_packet.data, level=LogLevel.ERROR
                )

    async def open(self) -> None:
        headers: dict | None = None
        if self.access_token is not None:
            headers = {"Authorization": f"Bearer {self.access_token}"}

        retry_iter = count(0) if self.max_retry < 0 else range(self.max_retry + 1)
        first_try, ok_flag = True, False
        # mypy's bullshit: Item "range" of "range | Iterator[int]" has no attribute "__next__"
        for _ in retry_iter:  # type: ignore[union-attr]
            if first_try:
                first_try = False
            else:
                await asyncio.sleep(self.retry_delay)

            try:
                self.conn = await websockets.connect(self.url, extra_headers=headers)
                ok_flag = True
                break

            except Exception as e:
                self.logger.warning(
                    f"ws 连接建立失败，{self.retry_delay}s 后自动重试。错误：{e}"
                )
                if "403" in str(e):
                    self.logger.warning("403 错误可能是 access_token 未配置或无效")
        if not ok_flag:
            raise IOError("重试已达最大次数，已放弃建立连接")

        self._tasks.append(asyncio.create_task(self._input_loop()))
        self._tasks.append(asyncio.create_task(self._output_loop()))
        self._opened = True
        self.logger.info("OneBot v11 正向 WebSocket IO 源已连接实现端")

    def opened(self) -> bool:
        return self._opened

    async def close(self) -> None:
        if self.opened():
            self.conn.close_timeout = 2
            await self.conn.close()
            await self.conn.wait_closed()
            for t in self._tasks:
                t.cancel()

            self._opened = False
            self.logger.info("OneBot v11 正向 WebSocket IO 源已停止运行")

    async def input(self) -> InPacket:
        return await self._in_buf.get()

    async def output(self, packet: OutPacket) -> EchoPacket:
        await self._out_buf.put(packet)
        if packet.echo_id is None:
            return EchoPacket(noecho=True)

        fut: Future[EchoPacket] = Future()
        self._echo_table[packet.echo_id] = (packet.action_type, fut)
        return await fut
