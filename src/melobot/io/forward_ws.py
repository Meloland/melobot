import asyncio
import time
from itertools import count

import websockets
import websockets.exceptions as wse

from ..base.abc import AbstractConnector, BotLife
from ..base.exceptions import BotConnectFailed, get_better_exc
from ..base.tools import get_rich_str
from ..base.typing import TYPE_CHECKING, ModuleType, Type

if TYPE_CHECKING:
    import websockets.legacy.client as wlc

    from ..base.abc import BotAction
    from ..bot.hook import BotHookBus
    from ..controller.dispatcher import BotDispatcher
    from ..controller.responder import BotResponder
    from ..models.event import BotEventBuilder
    from ..utils.logger import Logger


class ForwardWsConn(AbstractConnector):
    """正向 websocket 连接器
    """

    def __init__(
        self,
        connect_host: str,
        connect_port: int,
        max_retry: int = -1,
        retry_delay: float = 5.0,
        cd_time: float = 0.2,
    ) -> None:
        """初始化一个正向 websocket 连接器

        :param connect_host: 连接的 hostname
        :param connect_port: 连接的 port
        :param max_retry: 最大重试次数，默认 -1 代表无限次重试
        :param retry_delay: 重试间隔时间
        :param cd_time: action 发送冷却时间（用于防止风控）
        """
        super().__init__(max_retry, retry_delay, cd_time)
        self.logger: "Logger"
        self.url = f"ws://{connect_host}:{connect_port}"
        self.conn: "wlc.Connect"

        self._event_builder: Type["BotEventBuilder"]
        self._bot_bus: "BotHookBus"
        self._send_queue: asyncio.Queue["BotAction"] = asyncio.Queue()
        self._pre_send_time = time.time()
        self._common_dispatcher: "BotDispatcher"
        self._resp_dispatcher: "BotResponder"

    def _bind(
        self,
        common_dispatcher: "BotDispatcher",
        resp_dispatcher: "BotResponder",
        event_builder: Type["BotEventBuilder"],
        bot_bus: "BotHookBus",
        logger: "Logger",
    ) -> None:
        """绑定其他核心组件的方法。"""
        self._event_builder = event_builder
        self._bot_bus = bot_bus
        self.logger = logger
        self._common_dispatcher = common_dispatcher
        self._resp_dispatcher = resp_dispatcher

    async def _start(self) -> None:
        """启动连接."""
        iterator = count(0) if self.max_retry < 0 else range(self.max_retry + 1)
        for _ in iterator:
            try:
                self.conn = await websockets.connect(self.url)
                await self.conn.recv()

                self.logger.info("与连接适配器，建立了 ws 连接")
                await self._bot_bus.emit(BotLife.CONNECTED)
                self.logger.debug("CONNECTED hook 已完成")
                return
            except Exception as e:
                self.logger.warning(
                    f"ws 连接建立失败，{self.retry_delay}s 后自动重试。错误：{e}"
                )
                await asyncio.sleep(self.retry_delay)
        raise BotConnectFailed("连接重试已达最大重试次数，已放弃建立连接")

    async def _close(self) -> None:
        """关闭连接."""
        await self.conn.close()
        self.logger.info("已经关闭与连接适配器的连接")

    async def __aenter__(self) -> "ForwardWsConn":
        await self._start()
        return self

    async def __aexit__(
        self, exc_type: Type[Exception], exc_val: Exception, exc_tb: ModuleType
    ) -> bool:
        await self._close()
        if exc_type is None:
            return True
        elif exc_type == wse.ConnectionClosed:
            self.logger.info("连接适配器主动关闭, bot 将自动清理资源后关闭")
            return True
        elif exc_type == asyncio.CancelledError:
            return True
        else:
            self.logger.error(
                "连接适配器出现预期外的异常：\n" + get_better_exc(exc_val)
            )
            return False

    async def _send(self, action: "BotAction") -> None:
        """发送一个 action 给连接适配器。实际上是先提交到 send_queue."""
        await self._ready_signal.wait()

        if self.slack:
            self.logger.debug(f"action {id(action)} 因 slack 状态被丢弃")
            return
        await self._send_queue.put(action)
        self.logger.debug(f"action {id(action)} 已成功加入发送队列")

    async def _send_queue_watch(self) -> None:
        """真正的发送方法。从 send_queue 提取 action 并按照一些处理步骤操作."""
        await self._ready_signal.wait()

        try:
            while True:
                action = await self._send_queue.get()
                self.logger.debug(
                    f"action {id(action)} 准备发送，结构如下：\n"
                    + get_rich_str(action.__dict__)
                )
                await self._bot_bus.emit(BotLife.ACTION_PRESEND, action, wait=True)
                self.logger.debug(f"action {id(action)} presend hook 已完成")
                action_str = action.flatten()
                wait_time = self.cd_time - (time.time() - self._pre_send_time)
                self.logger.debug(f"action {id(action)} 冷却等待：{wait_time}")
                await asyncio.sleep(wait_time)
                await self.conn.send(action_str)
                self.logger.debug(f"action {id(action)} 已发送")
                self._pre_send_time = time.time()
        except asyncio.CancelledError:
            self.logger.debug("连接适配器发送队列监视任务已被结束")
        except wse.ConnectionClosed:
            self.logger.error("与连接适配器的通信已经断开，无法再执行操作")

    async def _listen(self) -> None:
        """从连接适配器接收一个事件，并转化为 BotEvent 对象传递给 dispatcher 处理."""
        await self._ready_signal.wait()

        try:
            while True:
                try:
                    raw_event = await self.conn.recv()
                    self.logger.debug(f"收到事件，未格式化的字符串：\n{raw_event}")
                    if raw_event == "":
                        continue
                    event = self._event_builder.build(raw_event)
                    self.logger.debug(
                        f"event {id(event)} 构建完成，结构：\n"
                        + get_rich_str(event.raw)
                    )
                    if event.is_resp_event():
                        asyncio.create_task(self._resp_dispatcher.respond(event))  # type: ignore
                    else:
                        asyncio.create_task(self._common_dispatcher.dispatch(event))  # type: ignore
                except wse.ConnectionClosed:
                    raise
                except Exception as e:
                    self.logger.error("bot life_task 抛出异常")
                    self.logger.error(f"异常点 raw_event：{raw_event}")
                    self.logger.error("异常回溯栈：\n" + get_better_exc(e))
                    self.logger.error("异常点局部变量：\n" + get_rich_str(locals()))
        except asyncio.CancelledError:
            self.logger.debug("bot 运行例程已停止")
        except wse.ConnectionClosed:
            self.logger.debug("与连接适配器的通信已经断开")

    async def _start_tasks(self) -> list[asyncio.Task]:
        return [
            asyncio.create_task(self._send_queue_watch()),
            asyncio.create_task(self._listen()),
        ]
