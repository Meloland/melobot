import asyncio
import time

import aiohttp
import aiohttp.log
import aiohttp.web
from aiohttp.client_exceptions import ClientConnectorError

from ..base.abc import AbstractConnector, BotLife
from ..base.typing import TYPE_CHECKING, ModuleType, Optional
from ..utils.logger import log_exc, log_obj

if TYPE_CHECKING:
    from ..base.abc import BotAction
    from ..models.event import ResponseEvent


class HttpConn(AbstractConnector):
    """HTTP 全双工连接器

    HTTP 全双工连接器将会同时开启 HTTP 服务端和客户端。

    客户端将会向 OneBot 实现程序发起 HTTP POST 请求用于传递行为操作，
    OneBot 实现程序将会向服务端发起 HTTP POST 请求用于事件上报。

    .. admonition:: 注意
       :class: caution

       HTTP 连接是无状态的，因此本连接器无法及时察觉 OneBot 实现程序掉线。只有在后续执行行为操作失败，或等待上报超时，才会发现 OneBot 实现程序掉线。

       本连接器目前暂不支持鉴权。
    """

    def __init__(
        self,
        onebot_host: str,
        onebot_port: int,
        listen_host: str,
        listen_port: int,
        cd_time: float = 0.2,
        allow_reconnect: bool = False,
        max_interval: Optional[float] = None,
    ) -> None:
        """初始化一个 HTTP 全双工连接器

        HTTP 全双工连接器与 ws 有所不同。它无法即时发现 OneBot 实现程序掉线。

        可以通过 `max_interval` 参数，启用“超时无上报则认为掉线”的功能。这一般要和 OneBot 实现程序的心跳功能一同使用。推荐设置值为心跳时间 + 1。

        当然即使不启用此功能，当本连接器尝试发送行为操作失败时，也会认为 OneBot 实现程序已掉线。

        :param onebot_host: onebot 实现程序 HTTP 服务的 host
        :param onebot_port: onebot 实现程序 HTTP 服务的 port
        :param listen_host: 此连接器服务端监听的 host
        :param listen_port: 此连接器服务端监听的 port
        :param cd_time: 行为操作冷却时间（用于防止风控）
        :param allow_reconnect: 是否等待 OneBot 实现程序重新上线。默认为 `False`，即检测到 OneBot 实现程序掉线，将直接停止 bot；若为 `True`，则会等待 OneBot 实现程序重新上线，等待时所有行为操作将阻塞
        :param max_interval: 等待 OneBot 实现程序上报的超时时间。超过此时间无任何上报，则认为已经掉线（默认值为 `None`，此时不启用此功能）
        """
        super().__init__(cd_time)
        #: onebot 实现程序提供服务的 base_url（形如：http://xxx:xxx）
        self.onebot_url = f"http://{onebot_host}:{onebot_port}"
        #: 本连接器服务端的 host
        self.host: str = listen_host
        #: 本连接器服务端的 port
        self.port: int = listen_port
        #: 本连接器服务端的站点对象
        self.serve_site: aiohttp.web.TCPSite
        #: 本连接器客户端的会话
        self.client_session: aiohttp.ClientSession
        #: 本连接器用于掉线判定的超时时间
        self.max_interval = max_interval

        self._send_queue: asyncio.Queue["BotAction"] = asyncio.Queue()
        self._pre_recv_time = time.time_ns()
        self._pre_send_time = time.time_ns()
        self._closed = asyncio.Event()
        self._close_lock = asyncio.Lock()
        self._onebot_onlined = asyncio.Event()
        self._allow_reconn = allow_reconnect
        self._connected_flag = False

    async def _start(self) -> None:
        """启动连接器"""
        # 打开一个会话用于与 onebot 实现程序建立连接
        self.client_session = aiohttp.ClientSession()
        # 开启 HTTP 服务端
        app = aiohttp.web.Application()
        app.add_routes([aiohttp.web.post("/", self._listen)])
        runner = aiohttp.web.AppRunner(app)
        await runner.setup()
        self.serve_site = aiohttp.web.TCPSite(runner, self.host, self.port)
        await self.serve_site.start()

        self.logger.info(
            "HTTP 通信就绪，等待 OneBot 实现程序上线中（即上报第一个事件）"
        )
        await self._onebot_onlined.wait()
        self.logger.info("HTTP 双向通信已建立")
        self._connected_flag = True

        if self.max_interval is not None and self.max_interval > 0:
            asyncio.create_task(self._overtime_monitor(self.max_interval))
        await self._bot_bus.emit(BotLife.FIRST_CONNECTED)
        self.logger.debug("FIRST_CONNECTED hook 已完成")

    async def _close(self) -> None:
        """关闭连接器"""
        if self._closed.is_set():
            return
        async with self._close_lock:
            if self._closed.is_set():
                return
            # 关闭 HTTP 服务端
            await self.serve_site.stop()
            # 关闭与 onebot 实现程序的连接会话
            await self.client_session.close()
            self._closed.set()
            self.logger.info("HTTP 双向通信已停止")

    async def _overtime_monitor(self, interval: float) -> None:
        """通过是否超时判断 OneBot 实现程序是否掉线"""
        try:
            while True:
                if (abs(time.time_ns() - self._pre_recv_time)) / 1e9 > interval:
                    self.logger.warning(
                        "OneBot 实现程序已掉线，正在等待 OneBot 实现程序重新上线"
                    )
                    self._onebot_onlined.clear()
                    await self._onebot_onlined.wait()
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            pass

    async def __aenter__(self) -> "HttpConn":
        asyncio.create_task(self._start())
        asyncio.create_task(self._watch_queue())
        return self

    async def __aexit__(
        self, exc_type: type[Exception], exc_val: Exception, exc_tb: ModuleType
    ) -> bool:
        await self._close()
        if await super().__aexit__(exc_type, exc_val, exc_tb):
            return True
        self.logger.error("连接器出现预期外的异常")
        log_exc(self.logger, locals(), exc_val)
        return False

    async def _listen(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        """从 OneBot 实现程序接收一个事件，并处理"""
        self._pre_recv_time = time.time_ns()

        await self._ready_signal.wait()
        if not self._onebot_onlined.is_set():
            self._onebot_onlined.set()
            if self._connected_flag:
                self.logger.info("OneBot 实现程序已经重新上线")
                await self._bot_bus.emit(BotLife.RECONNECTED)
                self.logger.debug("RECONNECTED hook 已完成")

        try:
            raw_event: dict = await request.json()
            if self.logger.check_level_flag("DEBUG"):
                self.logger.debug(f"收到事件，未格式化的字典对象：\n{raw_event}")
            event = self._event_builder.build(raw_event)
            if self.logger.check_level_flag("DEBUG"):
                log_obj(self.logger.debug, event.raw, f"event {event:hexid} 构建完成")
            asyncio.create_task(self._common_dispatcher.dispatch(event))  # type: ignore
        except Exception as e:
            self.logger.error("bot 连接器监听任务抛出异常")
            log_obj(self.logger.error, raw_event, "异常点 raw_event")
            log_exc(self.logger, locals(), e)
        finally:
            return aiohttp.web.Response(status=204)

    async def _send(self, action: "BotAction") -> None:
        """发送一个 action 给连接器，实际上是先提交到 send_queue"""
        await self._ready_signal.wait()
        await self._onebot_onlined.wait()

        if self.slack:
            self.logger.debug(f"action {action:hexid} 因 slack 状态被丢弃")
            return
        await self._send_queue.put(action)
        self.logger.debug(f"action {action:hexid} 已成功加入发送队列")

    async def _watch_queue(self) -> None:
        """真正的发送方法。从 send_queue 提取 action 并按照一些处理步骤操作"""

        async def take_action(action: "BotAction") -> None:
            try:
                _ = await self.client_session.post(
                    f"{self.onebot_url}/{action.type}", json=action.params
                )
                if action.resp_id is None:
                    return
                raw_resp: dict = await _.json()
                resp: "ResponseEvent" = self._event_builder.build(raw_resp)  # type: ignore
                resp.id = action.resp_id
                asyncio.create_task(self._resp_dispatcher.respond(resp))  # type: ignore
            except (RuntimeError, ClientConnectorError):
                if not self._allow_reconn:
                    self.logger.error("OneBot 实现程序已掉线，无法再执行行为操作")
                    await self._close()
                else:
                    self.logger.warning(
                        "OneBot 实现程序已掉线，正在等待 OneBot 实现程序重新上线"
                    )
                    self._onebot_onlined.clear()

        await self._ready_signal.wait()
        try:
            while True:
                action = await self._send_queue.get()
                await self._onebot_onlined.wait()
                if self.logger.check_level_flag("DEBUG"):
                    log_obj(
                        self.logger.debug,
                        action.__dict__,
                        f"action {action:hexid} 准备发送",
                    )
                await self._bot_bus.emit(BotLife.ACTION_PRESEND, action, wait=True)
                self.logger.debug(f"action {action:hexid} presend hook 已完成")
                wait_time = self.cd_time - (
                    (time.time_ns() - self._pre_send_time) / 1e9
                )
                self.logger.debug(f"action {action:hexid} 冷却等待：{wait_time}")
                await asyncio.sleep(wait_time)
                asyncio.create_task(take_action(action))
                self.logger.debug(f"action {action:hexid} 已发送")
                self._pre_send_time = time.time_ns()
        except asyncio.CancelledError:
            self.logger.debug("连接器发送队列监视任务已被结束")
