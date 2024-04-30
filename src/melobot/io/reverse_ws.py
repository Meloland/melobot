import asyncio
import http
import time

import websockets
import websockets.exceptions as wse
import websockets.server

from ..base.abc import AbstractConnector, BotAction, BotLife
from ..base.typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Optional,
    TracebackType,
    Union,
    cast,
)
from ..context.session import ActionResponse

if TYPE_CHECKING:
    from ..models.event import MessageEvent, MetaEvent, NoticeEvent, RequestEvent


class ReverseWsConn(AbstractConnector):
    """反向 websocket 连接器

    .. admonition:: 注意
       :class: caution

       注意：在 melobot 中，反向 websocket 连接器会开启一个 ws 服务端。但是这个服务端只接受一个客户端连接，后续其他连接将被拒绝。
    """

    def __init__(
        self,
        listen_host: str,
        listen_port: int,
        cd_time: float = 0.2,
        access_token: Optional[str] = None,
        reconnect: bool = False,
    ) -> None:
        """初始化一个反向 websocket连接器

        注意：服务提供路径为："/"

        :param listen_host: 监听的 host
        :param listen_port: 监听的 port
        :param cd_time: 行为操作冷却时间（用于防止风控）
        :param access_token: 本连接器用于鉴权的 access_token（建议从环境变量或配置中读取）
        :param reconnect: 是否允许客户端重新连接。默认为 `False`，即客户端连接后如果断连，将直接停止 bot；若为 `True`，则会等待客户端重连，等待时所有行为操作将阻塞
        """
        super().__init__(cd_time, reconnect)
        #: 监听的 host
        self.host: str = listen_host
        #: 监听的 port
        self.port: int = listen_port
        #: 服务端对象
        self.server: "websockets.server.WebSocketServer"
        #: 连接器操作鉴权的 token
        self.access_token = access_token

        self._conn: "websockets.server.WebSocketServerProtocol"
        self._send_queue: asyncio.Queue["BotAction"] = asyncio.Queue()
        self._pre_send_time = time.time_ns()

        self._conn_requested = False
        self._request_lock = asyncio.Lock()
        self._conn_ready = asyncio.Event()
        self._reconn_flag = False

    async def _req_check(
        self, path: str, headers: websockets.HeadersLike
    ) -> Optional[tuple[http.HTTPStatus, websockets.HeadersLike, bytes]]:
        """拦截握手请求，只允许一个客户端连接"""
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
                and headers.get("Authorization") != f"Bearer {self.access_token}"
            ):
                self.logger.warning("OneBot 实现程序的 access_token 不匹配，拒绝连接")
                return resp_403(auth_failed)

            self._conn_requested = True
            return None

    async def _run(self) -> None:
        """运行服务"""
        self._closed.clear()
        self.server = await websockets.serve(
            self._listen, self.host, self.port, process_request=self._req_check
        )
        self.logger.info("连接器启动了 ws 服务，等待 ws 连接中")

        await self._closed.wait()
        self.server.close()
        await self.server.wait_closed()
        self.logger.info("ws 服务已关闭")

    def _close(self) -> None:
        """关闭服务"""
        if self._closed.is_set():
            return
        else:
            self._closed.set()

    def _restore_wait(self) -> None:
        """在客户端主动断开连接后，重置到可以接受新连接的状态"""
        self.logger.warning("OneBot 实现程序主动断开连接，等待其重连中")
        self._conn_ready.clear()
        self._conn_requested = False
        del self._conn
        self._reconn_flag = True

    async def __aenter__(self) -> "ReverseWsConn":
        asyncio.create_task(self._run())
        asyncio.create_task(self._watch_queue())
        return self

    async def __aexit__(
        self, exc_type: type[Exception], exc_val: Exception, exc_tb: TracebackType
    ) -> bool:
        self._close()
        if await super().__aexit__(exc_type, exc_val, exc_tb):
            return True

        self.logger.error("连接器出现预期外的异常")
        self.logger.exc(locals=locals())
        return False

    async def _send(self, action: "BotAction") -> None:
        """发送一个 action 给连接器，实际上是先提交到 send_queue"""
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

                await self._conn.send(action_str)
                self.logger.debug(f"action {action:hexid} 已发送")
                self._pre_send_time = time.time_ns()

        except asyncio.CancelledError:
            self.logger.debug("连接器发送队列监视任务已被结束")
        except wse.ConnectionClosed:
            self.logger.error("与 OneBot 实现程序的通信已经停止，无法再执行行为操作")

    async def _listen(self, ws: "websockets.server.WebSocketServerProtocol") -> None:
        """从 OneBot 实现程序接收一个事件，并处理"""
        await self._ready_signal.wait()
        self._conn = ws
        self._conn_ready.set()
        self.logger.info("连接器与 OneBot 实现程序建立了 ws 连接")

        if not self._reconn_flag:
            await self._bot_bus.emit(BotLife.FIRST_CONNECTED)
            self.logger.debug("FIRST_CONNECTED hook 已完成")
        else:
            await self._bot_bus.emit(BotLife.RECONNECTED)
            self.logger.debug("RECONNECTED hook 已完成")

        try:
            while True:
                try:
                    raw = await self._conn.recv()

                    if self.logger._check_level("DEBUG"):
                        self.logger.obj(raw, "收到上报，未格式化的字符串")

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

                except wse.ConnectionClosed:
                    raise
                except Exception as e:
                    self.logger.error("bot 连接器监听任务抛出异常")
                    self.logger.obj(raw, "异常点的上报数据", level="ERROR")
                    self.logger.exc(locals=locals())

        except asyncio.CancelledError:
            self.logger.debug("连接器监听任务已停止")
        except wse.ConnectionClosed:
            self.logger.debug("连接器与 OneBot 实现程序的通信已经停止")

        finally:
            self._conn.close_timeout = 2
            if self._closed.is_set():
                return

            if not self.allow_reconn:
                self._close()
            else:
                self._restore_wait()
