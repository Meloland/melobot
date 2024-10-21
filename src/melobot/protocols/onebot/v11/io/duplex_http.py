# pylint: disable=duplicate-code
import asyncio
import hmac
import json
import time
from asyncio import Future

import aiohttp
import aiohttp.log
import aiohttp.web

from melobot.log import LogLevel

from .base import BaseIO
from .packet import EchoPacket, InPacket, OutPacket


class HttpIO(BaseIO):
    def __init__(
        self,
        onebot_host: str,
        onebot_port: int,
        serve_host: str,
        serve_port: int,
        secret: str | None = None,
        access_token: str | None = None,
        cd_time: float = 0.2,
    ) -> None:
        super().__init__(cd_time)
        self.onebot_url = f"http://{onebot_host}:{onebot_port}"
        self.host: str = serve_host
        self.port: int = serve_port
        self.serve_site: aiohttp.web.TCPSite
        self.client_session: aiohttp.ClientSession
        self.secret = secret
        self.access_token = access_token

        self._tasks: list[asyncio.Task] = []
        self._in_buf: asyncio.Queue[InPacket] = asyncio.Queue()
        self._out_buf: asyncio.Queue[OutPacket] = asyncio.Queue()
        self._echo_table: dict[str, tuple[str, Future[EchoPacket]]] = {}
        self._opened = asyncio.Event()
        self._pre_send_time = time.time_ns()

    async def _respond(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        if not self._opened.is_set():
            self._opened.set()

        data = await request.content.read()
        if data == b"":
            return aiohttp.web.Response(status=400)

        if self.secret is not None:
            sign = hmac.new(self.secret.encode(), data, "sha1").hexdigest()
            recv_sign = request.headers["X-Signature"][len("sha1=") :]

            if sign != recv_sign:
                self.logger.error("OneBot 实现程序鉴权不通过，本次上报数据将不会被处理")
                self.logger.generic_obj("试图上报的数据", data, level=LogLevel.ERROR)
                return aiohttp.web.Response(status=403)

        try:
            raw = json.loads(data.decode())
            self.logger.generic_obj("收到上报，未格式化的字典", raw, level=LogLevel.DEBUG)
            await self._in_buf.put(InPacket(time=raw["time"], data=raw))
        except Exception:
            self.logger.exception("OneBot v11 HTTP IO 源输入异常")
            self.logger.generic_obj("异常点局部变量", locals(), level=LogLevel.ERROR)
            self.logger.generic_obj("异常点的上报数据", raw, level=LogLevel.ERROR)

        finally:
            return (  # pylint: disable=return-in-finally,lost-exception
                aiohttp.web.Response(status=204)
            )

    async def _output_loop(self) -> None:
        while True:
            try:
                out_packet = await self._out_buf.get()
                wait_time = self.cd_time - ((time.time_ns() - self._pre_send_time) / 1e9)
                await asyncio.sleep(wait_time)
                asyncio.create_task(self._handle_output(out_packet))
                self._pre_send_time = time.time_ns()
            except Exception:
                self.logger.exception("OneBot v11 HTTP IO 源输出异常")
                self.logger.generic_obj("异常点局部变量", locals(), level=LogLevel.ERROR)
                self.logger.generic_obj(
                    "异常点的发送数据", out_packet.data, level=LogLevel.ERROR
                )

    async def _handle_output(self, packet: OutPacket) -> None:
        try:
            headers: dict | None = None
            if self.access_token is not None:
                headers = {"Authorization": f"Bearer {self.access_token}"}

            http_resp = await self.client_session.post(
                f"{self.onebot_url}/{packet.action_type}",
                json=packet.action_params,
                headers=headers,
            )
            if packet.echo_id is None:
                return

            raw = await http_resp.json()
            echo_id = raw.get("echo")
            if echo_id in (None, ""):
                return

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
        except aiohttp.ContentTypeError:
            self.logger.error(
                "OneBot v11 HTTP IO 源无法解析上报数据。可能是 access_token 未配置或错误"
            )
        except Exception:
            self.logger.exception("OneBot v11 HTTP IO 源输出异常")
            self.logger.generic_obj("异常点局部变量", locals(), level=LogLevel.ERROR)
            self.logger.generic_obj("异常点的发送数据", packet.data, level=LogLevel.ERROR)

    async def open(self) -> None:
        self.client_session = aiohttp.ClientSession()
        app = aiohttp.web.Application()
        app.add_routes([aiohttp.web.post("/", self._respond)])
        runner = aiohttp.web.AppRunner(app)

        await runner.setup()
        self.serve_site = aiohttp.web.TCPSite(runner, self.host, self.port)
        await self.serve_site.start()
        self._tasks.append(asyncio.create_task(self._output_loop()))

        self.logger.info("OneBot v11 HTTP IO 源就绪，等待实现端上线中")
        await self._opened.wait()
        self.logger.info("OneBot v11 HTTP IO 源双向通信已建立")

    def opened(self) -> bool:
        return self._opened.is_set()

    async def close(self) -> None:
        if self.opened():
            await self.serve_site.stop()
            await self.client_session.close()
            for t in self._tasks:
                t.cancel()

            self._opened.clear()
            self.logger.info("OneBot v11 HTTP IO 源已停止运行")

    async def input(self) -> InPacket:
        return await self._in_buf.get()

    async def output(self, packet: OutPacket) -> EchoPacket:
        await self._out_buf.put(packet)
        if packet.echo_id is None:
            return EchoPacket(noecho=True)

        fut: Future[EchoPacket] = Future()
        self._echo_table[packet.echo_id] = (packet.action_type, fut)
        return await fut
