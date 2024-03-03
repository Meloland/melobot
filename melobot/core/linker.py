import asyncio as aio
import time
import traceback
from itertools import count

import websockets
import websockets.exceptions as wse

from ..models.action import BotAction
from ..models.bot import BotHookBus
from ..models.event import BotEventBuilder
from ..types.core import IActionSender, IEventDispatcher, IRespDispatcher
from ..types.exceptions import *
from ..types.models import BotLife
from ..types.typing import *
from ..utils.logger import Logger


class BotLinker(IActionSender):
    """
    Bot 连接模块通过连接适配器的代理，完成事件接收与行为发送。
    """

    def __init__(
        self,
        connect_host: str,
        connect_port: int,
        max_retry: int,
        retry_delay: int,
        send_interval: float,
        logger: Logger,
    ) -> None:
        super().__init__()
        self.url = f"ws://{connect_host}:{connect_port}"
        self.conn = None

        self.logger = logger
        self.slack = False
        self.max_retry_num = max_retry
        self.retry_delay = retry_delay if retry_delay > 0 else 0

        self._ready_signal = aio.Event()
        self._send_lock = aio.Lock()
        self._rest_time = send_interval
        self._pre_send_time = time.time()
        self._common_dispatcher: IEventDispatcher
        self._resp_dispatcher: IRespDispatcher

    def bind(
        self,
        common_dispatcher: IEventDispatcher,
        resp_dispatcher: IRespDispatcher,
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
                self.logger.info("与连接适配器，建立了 ws 连接")
                await BotHookBus.emit(BotLife.CONNECTED)
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
        self.logger.info("已经关闭与连接适配器的连接")

    async def __aenter__(self) -> "BotLinker":
        await self._start()
        return self

    async def __aexit__(
        self, exc_type: Exception, exc_val: str, exc_tb: traceback
    ) -> None:
        if exc_type == wse.ConnectionClosedError:
            self.logger.warning("连接适配器主动关闭, bot 将自动清理资源后关闭")
        await self._close()

    async def send(self, action: BotAction) -> None:
        """
        发送一个 action 给连接适配器
        """
        await self._ready_signal.wait()
        await BotHookBus.emit(BotLife.ACTION_PRESEND, action, wait=True)
        if self.slack:
            return

        try:
            async with self._send_lock:
                action_str = action.flatten()
                await aio.sleep(self._rest_time - (time.time() - self._pre_send_time))
                await self.conn.send(action_str)
                self._pre_send_time = time.time()
        except aio.CancelledError:
            self.logger.warning("发生一次递归重发")
            await self.send(action)
        except wse.ConnectionClosed:
            self.logger.error("与连接适配器的通信已经断开，无法再执行操作")

    async def listen(self) -> None:
        """
        从连接适配器接收一个事件，并转化为 BotEvent 对象传递给 dispatcher 处理
        """
        await self._ready_signal.wait()

        try:
            while True:
                try:
                    raw_event = await self.conn.recv()
                    if raw_event == "":
                        continue
                    event = BotEventBuilder.build(raw_event)
                    if event.is_resp():
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
