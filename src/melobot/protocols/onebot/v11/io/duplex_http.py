import asyncio
import hmac
import json
import time
from asyncio import Future

import aiohttp
import aiohttp.log
import aiohttp.web

from melobot import report_exc
from melobot.io import SourceLifeSpan
from melobot.log import LogLevel

from .base import BaseIOSource
from .packet import EchoPacket, InPacket, OutPacket


class HttpIO(BaseIOSource):
    def __init__(
        self,
        onebot_url: str,
        serve_host: str,
        serve_port: int,
        secret: str | None = None,
        access_token: str | None = None,
        cd_time: float = 0,
    ) -> None:
        super().__init__(cd_time)
        self.onebot_url = onebot_url
        self.host: str = serve_host
        self.port: int = serve_port
        self.serve_site: aiohttp.web.TCPSite
        self.client_session: aiohttp.ClientSession
        self.secret = secret
        self.access_token = access_token

        self._tasks: list[asyncio.Task] = []
        self._in_buf: asyncio.Queue[InPacket] = asyncio.Queue()
        self._out_buf: asyncio.Queue[OutPacket] = asyncio.Queue()
        self._pre_send_time = time.time_ns()

        self._echo_table: dict[str, tuple[str, Future[EchoPacket]]] = {}
        self._opened = asyncio.Event()
        self._lock = asyncio.Lock()

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
                self.logger.warning("OneBot 实现程序鉴权不通过，本次上报数据将不会被处理")
                self.logger.generic_obj("试图上报的数据", data, level=LogLevel.WARNING)
                return aiohttp.web.Response(status=403)

        try:
            raw = json.loads(data.decode())
            if (
                self._hook_bus.get_evoke_time(SourceLifeSpan.STARTED) != -1
                and raw.get("post_type") == "meta_event"
                and raw.get("meta_event_type") == "lifecycle"
                and raw.get("sub_type") == "connect"
            ):
                await self._hook_bus.emit(SourceLifeSpan.RESTARTED, False)
            self.logger.generic_obj("收到上报，未格式化的字典", str(raw), level=LogLevel.DEBUG)
            await self._in_buf.put(InPacket(time=raw["time"], data=raw))

        except Exception as e:
            report_exc(e, msg="OneBot v11 HTTP IO 源输入异常", var=raw)

        finally:
            return aiohttp.web.Response(status=204)

    async def _output_loop(self) -> None:
        while True:
            try:
                await self._opened.wait()

                out_packet = await self._out_buf.get()
                wait_time = self.cd_time - ((time.time_ns() - self._pre_send_time) / 1e9)
                await asyncio.sleep(wait_time)
                asyncio.create_task(self._handle_output(out_packet))
                self._pre_send_time = time.time_ns()

            except asyncio.CancelledError:
                raise

            except Exception as e:
                report_exc(e, msg="OneBot v11 HTTP IO 源输出异常", var=locals())

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
        except Exception as e:
            report_exc(e, msg="OneBot v11 HTTP IO 源输出异常", var=packet.data)

    async def open(self) -> None:
        if self.opened():
            return

        async with self._lock:
            if self.opened():
                return

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
        if not self.opened():
            return

        async with self._lock:
            if not self.opened():
                return

            await self.serve_site.stop()
            await self.client_session.close()
            for t in self._tasks:
                t.cancel()
            if len(self._tasks):
                await asyncio.wait(self._tasks)
            self._tasks.clear()

            self._opened.clear()
            self.logger.info("OneBot v11 HTTP IO 源已停止运行")

    async def input(self) -> InPacket:
        return await self._in_buf.get()

    async def output(self, packet: OutPacket) -> EchoPacket:
        await self._out_buf.put(packet)
        if packet.echo_id is None:
            return EchoPacket(noecho=True)

        fut: Future[EchoPacket] = asyncio.get_running_loop().create_future()
        self._echo_table[packet.echo_id] = (packet.action_type, fut)
        return await fut
