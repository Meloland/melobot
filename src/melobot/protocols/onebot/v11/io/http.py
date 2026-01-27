from __future__ import annotations

import asyncio
import hmac
import json
import time
from asyncio import Future

import aiohttp
import aiohttp.web

from melobot.io import SourceLifeSpan
from melobot.log import LogLevel, log_exc, logger
from melobot.utils import truncate

from .base import BaseIOSource, InstCounter
from .packet import EchoPacket, InPacket, OutPacket


class HTTPDuplex(InstCounter, BaseIOSource):
    def __init__(
        self,
        onebot_url: str,
        serve_host: str,
        serve_port: int,
        secret: str | None = None,
        access_token: str | None = None,
        cd_time: float = 0,
        *,
        name: str | None = None,
    ) -> None:
        super().__init__(cd_time)
        self.name = f"[OB11 双向 http #{self.INSTANCE_COUNT}]" if name is None else name
        self._hook_bus.set_tag(self.name)

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
                logger.generic_lazy(
                    f"{self.name} 拒绝了收到的数据，因为签名验证失败：\n%s",
                    lambda: truncate(str(data)),
                    level=LogLevel.WARNING,
                )
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
            logger.generic_lazy(
                f"{self.name} 收到数据：\n%s", lambda: truncate(str(raw)), level=LogLevel.DEBUG
            )
            self._in_buf.put_nowait(InPacket(time=raw["time"], data=raw))

        except Exception as e:
            local_vars = locals()
            local_vars.pop("sign", None)
            local_vars.pop("recv_sign", None)
            local_vars.pop("raw", None)
            if (val := local_vars.pop("data", None)) is not None:
                local_vars["data"] = truncate(val)
            log_exc(e, msg=f"{self.name} 接收数据时抛出异常", obj=local_vars)

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
                log_exc(
                    e,
                    msg=f"{self.name} 发送数据时抛出异常",
                    obj={k: truncate(str(v)) for k, v in locals().items()},
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
            logger.error(f"{self.name} 无法解析收到的数据。可能是 access_token 未配置或错误")
        except Exception as e:
            log_exc(e, msg=f"{self.name} 发送数据并等待响应时抛出异常", obj=truncate(packet.data))

    async def open(self) -> None:
        if self.opened():
            return

        async with self._lock:
            if self.opened():
                return

            self.client_session = aiohttp.ClientSession()
            logger.info(f"{self.name} 已设置向 OB 实现端 ({self.onebot_url}) 发送数据")
            app = aiohttp.web.Application()
            app.add_routes([aiohttp.web.post("/", self._respond)])
            runner = aiohttp.web.AppRunner(app)
            await runner.setup()
            self.serve_site = aiohttp.web.TCPSite(runner, self.host, self.port)
            await self.serve_site.start()
            logger.info(f"{self.name} 启动了 http 服务端 (http://{self.host}:{self.port})")
            self._tasks.append(asyncio.create_task(self._output_loop()))

            logger.info(f"{self.name} 准备就绪，等待 OB 实现端上线中")
            await self._opened.wait()
            logger.info(f"{self.name} 双向通信已建立")

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
            logger.info(f"{self.name} 已停止工作")

    async def input(self) -> InPacket:
        return await self._in_buf.get()

    async def output(self, packet: OutPacket) -> EchoPacket:
        if self._out_buf.qsize() > 100:
            logger.warning(f"{self.name} 输出缓冲区积压过多数据，请保证连接畅通或减少操作请求频率")
            raise RuntimeError("输出缓冲区溢出，操作请求被丢弃")
        self._out_buf.put_nowait(packet)
        if packet.echo_id is None:
            return EchoPacket(noecho=True)

        fut: Future[EchoPacket] = asyncio.get_running_loop().create_future()
        if len(self._echo_table) > 256:
            logger.warning(
                f"{self.name} echo 标识映射表溢出，开始丢弃操作请求。请保证连接畅通或减少操作请求频率"
            )
            raise RuntimeError("echo 标识映射表溢出，操作请求被丢弃")
        self._echo_table[packet.echo_id] = (packet.action_type, fut)
        return await fut
