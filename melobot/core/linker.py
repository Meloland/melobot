import asyncio as aio
import time
import traceback
from logging import Logger

import websockets
import websockets.exceptions as wse

from ..interface.core import (IActionSender, IEventDispatcher, IMetaDispatcher,
                              IRespDispatcher)
from ..interface.typing import *
from ..models.action import BotAction
from ..models.event import BotEventBuilder


# TODO: 完成连接协议和对应适配器
class BotLinker(IActionSender):
    """
    Bot 连接模块通过连接适配器的代理，完成事件接收与行为发送。
    """
    def __init__(self, connect_host: str, connect_port: int, send_interval: float, logger: Logger) -> None:
        super().__init__()
        self.url = f"ws://{connect_host}:{connect_port}"
        self.conn = None
        self.rest_time = send_interval
        self._pre_send_time = time.time()
        self._logger = logger

        self._send_lock = aio.Lock()
        self._ready_signal = aio.Event()
        self.common_dispatcher: IEventDispatcher
        self.resp_dispatcher: IRespDispatcher
        self.meta_dispatcher: IMetaDispatcher

    def bind(self, common_dispatcher: IEventDispatcher, resp_dispatcher: IRespDispatcher, 
             meta_dispatcher: IMetaDispatcher) -> None:
        """
        绑定其他核心组件的方法。
        """
        self.common_dispatcher = common_dispatcher
        self.resp_dispatcher = resp_dispatcher
        self.meta_dispatcher = meta_dispatcher
        self._ready_signal.set()
    
    async def _start(self) -> None:
        """
        启动连接
        """
        self.conn = await websockets.connect(self.url)
        await self.conn.recv()
        self._logger.info("与连接适配器，建立了 ws 连接")

    async def _close(self) -> None:
        """
        关闭连接
        """
        await self.conn.close()
        self._logger.info("已经关闭与连接适配器的连接")

    async def __aenter__(self) -> "BotLinker":
        await self._start()
        return self
    
    async def __aexit__(self, exc_type: Exception, exc_val: str, exc_tb: traceback) -> None:
        if exc_type == wse.ConnectionClosedError:
            self._logger.warning("连接适配器主动关闭, bot 将自动清理资源后关闭")
        await self._close()

    async def send(self, action: BotAction) -> None:
        """
        发送一个 action 给连接适配器
        """
        await self._ready_signal.wait()

        try:
            async with self._send_lock:
                action_str = action.flatten()
                await aio.sleep(self.rest_time-(time.time()-self._pre_send_time))
                await self.conn.send(action_str)
                self._pre_send_time = time.time()
        except aio.CancelledError:
            # FIXME: 并发度 >=3 sleep 会被取消
            # 咱时找不到问题，但是可以通过递归重发解决。递归深度和数量在可以接收的范围内
            self._logger.warning("发生一次递归重发")
            await self.send(action)
        except wse.ConnectionClosed:
            self._logger.error("与连接适配器的通信已经断开，无法再执行操作")

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
                        aio.create_task(self.resp_dispatcher.dispatch(event))
                    elif event.is_meta():
                        aio.create_task(self.meta_dispatcher.dispatch(event))
                    else:
                        aio.create_task(self.common_dispatcher.dispatch(event))
                except wse.ConnectionClosed:
                    raise
                except Exception as e:
                    self._logger.debug(traceback.format_exc())
                    self._logger.error(f"bot 运行例程抛出异常：{e.__class__.__name__} {e}，当前事件为：{raw_event}。bot 仍在运行。")
        except aio.CancelledError:
            self._logger.debug("bot 运行例程已停止")