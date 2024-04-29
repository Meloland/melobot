import asyncio
import time
from itertools import count

import websockets
from websockets.exceptions import ConnectionClosed

from ..base.abc import AbstractConnector, BotLife
from ..base.typing import TYPE_CHECKING, Optional, TracebackType, Type, Union, cast
from ..context.session import ActionResponse

if TYPE_CHECKING:
    import websockets.client

    from ..base.abc import BotAction
    from ..models.event import MessageEvent, MetaEvent, NoticeEvent, RequestEvent


class ForwardWsConn(AbstractConnector):
    """正向 websocket 连接器

    .. admonition:: 注意
       :class: caution

       在 melobot 中，正向 websocket 连接器会开启一个 ws 客户端。这个客户端只能和一个服务端通信。
    """

    def __init__(
        self,
        connect_host: str,
        connect_port: int,
        max_retry: int = -1,
        retry_delay: float = 4.0,
        cd_time: float = 0.2,
        access_token: Optional[str] = None,
        reconnect: bool = False,
    ) -> None:
        """初始化一个正向 websocket 连接器

        注意：会向路径 "/" 发起行为操作

        :param connect_host: 连接的 host
        :param connect_port: 连接的 port
        :param max_retry: 连接最大重试次数，默认 -1 代表无限次重试
        :param retry_delay: 连接重试间隔时间
        :param cd_time: 行为操作冷却时间（用于防止风控）
        :param access_token: 本连接器操作鉴权的 access_token（建议从环境变量或配置中读取）
        :param reconnect: 建立连接失败是否重连。默认为 `False`，即服务端断线直接停止 bot；若为 `True`，则会按照 `max_retry`, `retry_delay` 不断尝试重连，重连成功前时所有行为操作将阻塞。
        """
        super().__init__(cd_time, reconnect)
        #: 连接失败最大重试次数
        self.max_retry: int = max_retry
        #: 连接失败重试间隔
        self.retry_delay: float = retry_delay if retry_delay > 0 else 0
        #: ws 连接的 url（形如：ws://xxx:xxx）
        self.url = f"ws://{connect_host}:{connect_port}"
        #: 连接对象（未建立连接时为空，连接建立后可认为一定不为空）
        self.conn: Optional["websockets.client.WebSocketClientProtocol"] = None
        #: 连接器操作鉴权的 token
        self.access_token = access_token

        self._send_queue: asyncio.Queue["BotAction"] = asyncio.Queue()
        self._pre_send_time = time.time_ns()

        self._conn_ready = asyncio.Event()
        self._reconn_flag = False
        self._run_lock = asyncio.Lock()

    async def _run(self) -> None:
        """运行客户端"""
        headers: dict | None = None
        if self.access_token is not None:
            headers = {"Authorization": f"Bearer {self.access_token}"}

        async with self._run_lock:
            self._closed.clear()
            ok_flag = False
            retry_iter = count(0) if self.max_retry < 0 else range(self.max_retry + 1)
            first_try = True

            for _ in retry_iter:
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
                self.logger.error("重试已达最大次数，已放弃建立连接")
                self._close()
                for task in asyncio.all_tasks():
                    task.cancel()
                return

            try:
                self.logger.info("连接器与 OneBot 实现程序建立了 ws 连接")
                self._conn_ready.set()
                asyncio.create_task(self._listen())
                await self._closed.wait()
            finally:
                if self.conn is not None:
                    await self.conn.close()
                    await self.conn.wait_closed()
                    self.logger.info("与 OneBot 实现程序的连接已关闭")

    def _close(self) -> None:
        """关闭连接"""
        if self._closed.is_set():
            return
        else:
            self.allow_reconn = False
            self._closed.set()

    async def _reconnect(self) -> None:
        """关闭已经无效的连接，随后开始尝试建立新连接"""
        self._conn_ready.clear()
        self._closed.set()
        self._reconn_flag = True
        asyncio.create_task(self._run())

    async def __aenter__(self) -> "ForwardWsConn":
        asyncio.create_task(self._run())
        asyncio.create_task(self._watch_queue())
        return self

    async def __aexit__(
        self, exc_type: Type[Exception], exc_val: Exception, exc_tb: TracebackType
    ) -> bool:
        self._close()
        if await super().__aexit__(exc_type, exc_val, exc_tb):
            return True

        self.logger.error("连接器出现预期外的异常")
        self.logger.exc(locals=locals())
        return False

    async def _send(self, action: "BotAction") -> None:
        """发送一个 action 给连接器。实际上是先提交到 send_queue"""
        await self._ready_signal.wait()
        await self._conn_ready.wait()

        if self.slack:
            self.logger.debug(f"action {action:hexid} 因 slack 状态被丢弃")
            return

        await self._send_queue.put(action)
        self.logger.debug(f"action {action:hexid} 已成功加入发送队列")

    async def _watch_queue(self) -> None:
        """真正的发送方法。从 send_queue 提取 action 并按照一些处理步骤操作"""
        await self._ready_signal.wait()

        try:
            while True:
                action = await self._send_queue.get()
                await self._conn_ready.wait()

                if self.logger._check_level("DEBUG"):
                    self.logger.obj(action.__dict__, f"action {action:hexid} 准备发送")

                await self._bot_bus.emit(BotLife.ACTION_PRESEND, action, wait=True)
                self.logger.debug(f"action {action:hexid} presend hook 已完成")

                action_str = action.flatten()
                wait_time = self.cd_time - ((time.time_ns() - self._pre_send_time) / 1e9)
                await asyncio.sleep(wait_time)

                self.conn = cast("websockets.client.WebSocketClientProtocol", self.conn)
                await self.conn.send(action_str)
                self.logger.debug(f"action {action:hexid} 已发送")
                self._pre_send_time = time.time_ns()

        except asyncio.CancelledError:
            self.logger.debug("连接器发送队列监视任务已被结束")
        except ConnectionClosed:
            self.logger.error("与 OneBot 实现程序的通信已经停止，无法再执行操作")

    async def _listen(self) -> None:
        """从 OneBot 实现程序接收一个事件，并处理"""
        await self._ready_signal.wait()
        await self._conn_ready.wait()

        if not self._reconn_flag:
            await self._bot_bus.emit(BotLife.FIRST_CONNECTED)
            self.logger.debug("FIRST_CONNECTED hook 已完成")
        else:
            await self._bot_bus.emit(BotLife.RECONNECTED)
            self.logger.debug("RECONNECTED hook 已完成")

        try:
            while True:
                try:
                    self.conn = cast(
                        "websockets.client.WebSocketClientProtocol", self.conn
                    )
                    raw = await self.conn.recv()
                    if self.logger._check_level("DEBUG"):
                        self.logger.obj(raw, "收到上报，未格式化的字符串")

                    if raw == "":
                        continue

                    event = self._event_builder.try_build(raw)
                    if event is None:
                        resp = ActionResponse(raw)
                        asyncio.create_task(self._resp_dispatcher.respond(resp))
                    else:
                        event = cast(
                            Union[
                                "MessageEvent",
                                "RequestEvent",
                                "MetaEvent",
                                "NoticeEvent",
                            ],
                            event,
                        )
                        asyncio.create_task(self._common_dispatcher.dispatch(event))

                except ConnectionClosed:
                    raise
                except Exception as e:
                    self.logger.error("bot 连接器监听任务抛出异常")
                    self.logger.obj(raw, "异常点的上报数据", level="ERROR")
                    self.logger.exc(locals=locals())

        except asyncio.CancelledError:
            self.logger.debug("连接器监听任务已停止")
        except ConnectionClosed:
            self.logger.debug("连接器与 OneBot 实现程序的通信已经停止")

        finally:
            self.conn = cast("websockets.client.WebSocketClientProtocol", self.conn)
            self.conn.close_timeout = 2
            if self._closed.is_set():
                return

            if not self.allow_reconn:
                self._close()
            else:
                await self._reconnect()
