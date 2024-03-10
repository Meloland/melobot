import asyncio as aio
import time
import traceback
from itertools import count

import websockets
import websockets.exceptions as wse

from ..types.abc import AbstractDispatcher, AbstractSender, BotLife
from ..types.exceptions import *
from ..types.typing import *

if TYPE_CHECKING:
    from ..models.event import BotEventBuilder
    from ..plugin.bot import BotHookBus
    from ..types.abc import BotAction
    from ..utils.logger import Logger


class BotLinker(AbstractSender):
    """
    Bot 连接模块通过连接驱动器的代理，完成事件接收与行为发送。
    """

    def __init__(
        self,
        connect_host: str,
        connect_port: int,
        max_retry: int,
        retry_delay: int,
        send_interval: float,
        event_builder: Type["BotEventBuilder"],
        bot_bus: Type["BotHookBus"],
        logger: "Logger",
    ) -> None:
        super().__init__()
        self.url = f"ws://{connect_host}:{connect_port}"
        self.conn = None

        self.logger = logger
        self.slack = False
        self.max_retry_num = max_retry
        self.retry_delay = retry_delay if retry_delay > 0 else 0

        self._event_builder = event_builder
        self._bot_bus = bot_bus
        self._send_queue: aio.Queue["BotAction"] = aio.Queue()
        self._ready_signal = aio.Event()
        self._rest_time = send_interval
        self._pre_send_time = time.time()
        self._common_dispatcher: AbstractDispatcher
        self._resp_dispatcher: AbstractDispatcher

    def bind(
        self,
        common_dispatcher: AbstractDispatcher,
        resp_dispatcher: AbstractDispatcher,
    ) -> None:
        """
        绑定其他核心组件的方法。
        """
        self._common_dispatcher = common_dispatcher
        self._resp_dispatcher = resp_dispatcher
        self._ready_signal.set()

    async def _start(self) -> None:
        """
        启动连接
        """
        iterator = count(0) if self.max_retry_num < 0 else range(self.max_retry_num + 1)
        for _ in iterator:
            try:
                self.conn = await websockets.connect(self.url)
                await self.conn.recv()
                self.logger.info("与连接驱动器，建立了 ws 连接")
                await self._bot_bus.emit(BotLife.CONNECTED)
                return
            except Exception as e:
                self.logger.warning(
                    f"ws 连接建立失败，{self.retry_delay}s 后自动重试。错误：{e}"
                )
                await aio.sleep(self.retry_delay)
        raise BotConnectFailed("连接重试已达最大重试次数，已放弃建立连接")

    async def _close(self) -> None:
        """
        关闭连接
        """
        await self.conn.close()
        self.logger.info("已经关闭与连接驱动器的连接")

    async def __aenter__(self) -> "BotLinker":
        await self._start()
        return self

    async def __aexit__(
        self, exc_type: Exception, exc_val: str, exc_tb: ModuleType
    ) -> None:
        if exc_type == wse.ConnectionClosedError:
            self.logger.warning("连接驱动器主动关闭, bot 将自动清理资源后关闭")
        await self._close()

    async def send(self, action: "BotAction") -> None:
        """
        发送一个 action 给连接驱动器。实际上是先提交到 send_queue
        """
        await self._ready_signal.wait()
        await self._send_queue.put(action)

    async def send_queue_watch(self) -> None:
        """
        真正的发送方法。从 send_queue 提取 action 并按照一些处理步骤操作
        """
        await self._ready_signal.wait()
        try:
            while True:
                action = await self._send_queue.get()
                await self._bot_bus.emit(BotLife.ACTION_PRESEND, action, wait=True)
                if self.slack:
                    return
                action_str = action.flatten()
                await aio.sleep(self._rest_time - (time.time() - self._pre_send_time))
                await self.conn.send(action_str)
                self._pre_send_time = time.time()
        except aio.CancelledError:
            self.logger.debug("连接适配器发送队列监视任务已被结束")
        except wse.ConnectionClosed:
            self.logger.error("与连接驱动器的通信已经断开，无法再执行操作")

    async def listen(self) -> None:
        """
        从连接驱动器接收一个事件，并转化为 BotEvent 对象传递给 dispatcher 处理
        """
        await self._ready_signal.wait()

        try:
            while True:
                try:
                    raw_event = await self.conn.recv()
                    if raw_event == "":
                        continue
                    event = self._event_builder.build(raw_event)
                    if event.is_resp_event():
                        aio.create_task(self._resp_dispatcher.dispatch(event))
                    else:
                        aio.create_task(self._common_dispatcher.dispatch(event))
                except wse.ConnectionClosed:
                    raise
                except Exception as e:
                    self.logger.error(
                        f"bot life_task 抛出异常：[{e.__class__.__name__}] {e}"
                    )
                    self.logger.debug(f"异常点的事件记录为：{raw_event}")
                    self.logger.debug(
                        "异常回溯栈：\n" + traceback.format_exc().strip("\n")
                    )
        except aio.CancelledError:
            self.logger.debug("bot 运行例程已停止")
