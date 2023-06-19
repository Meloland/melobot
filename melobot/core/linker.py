import asyncio as aio
import sys
import time
import traceback
from asyncio import Lock
from logging import Logger

import websockets
import websockets.exceptions as wse

from ..interface.core import IEventDispatcher, IMetaDispatcher, IRespDispatcher, IActionSender
from ..models.action import BotAction
from ..models.event import BotEventBuilder


class BotLinker(IActionSender):
    """
    Bot 连接模块，负责与 cq 建立连接。
    负责发送 action 到 cq，以及运行 cq 事件监听响应例程。
    """
    def __init__(self, connect_host: str, connect_port: int, send_interval: float, logger: Logger) -> None:
        super().__init__()
        self.url = f"ws://{connect_host}:{connect_port}"
        self.connector = None
        self.send_interval = send_interval
        self._pre_send_time = time.time()
        self._logger = logger


        self._send_lock = Lock()
        self._ready_signal = aio.Event()
        self.common_dispatcher: IEventDispatcher
        self.resp_dispatcher: IRespDispatcher
        self.meta_dispatcher: IMetaDispatcher

    def bind(self, common_dispatcher: IEventDispatcher, resp_dispatcher: IRespDispatcher, 
             meta_dispatcher: IMetaDispatcher) -> None:
        """
        绑定其他核心组件的方法。独立出来，方便上层先创建实例再调用
        """
        self.common_dispatcher = common_dispatcher
        self.resp_dispatcher = resp_dispatcher
        self.meta_dispatcher = meta_dispatcher
        self._ready_signal.set()

    async def _start(self) -> None:
        """
        启动连接
        """
        self.connector = await websockets.connect(self.url)
        await self.connector.recv()
        self._logger.info("与 cq 成功建立了 ws 连接")

    async def _close(self) -> None:
        """
        关闭连接
        """
        await self.connector.close()
        self._logger.info("已经关闭与 cq 的连接")

    async def __aenter__(self) -> "BotLinker":
        await self._start()
        return self
    
    async def __aexit__(self, exc_type: Exception, exc_val: str, exc_tb: traceback) -> None:
        await self._close()

    async def send(self, action: BotAction) -> None:
        """
        发送一个 action 给 cq
        """
        # 阻塞等待连接模块绑定调度组件
        await self._ready_signal.wait()

        try:
            async with self._send_lock:
                action_str = action.flatten()
                await aio.sleep(self.send_interval-(time.time()-self._pre_send_time))
                await self.connector.send(action_str)
                self._pre_send_time = time.time()
        except wse.ConnectionClosed:
            self._logger.error("与 cq 的连接已经断开，无法再执行操作")

    async def recv_routine(self) -> None:
        """
        从 cq 接收一个上报的事件，并转化为 BotEvent 对象传递给 dispatcher 处理
        """
        await self._ready_signal.wait()

        try:
            while True:
                try:
                    raw_event = await self.connector.recv()
                    if raw_event == "":
                        continue
                    
                    # 事件分发处理不是连接模块的职责，分类后交给外界处理
                    event = BotEventBuilder.build(raw_event)
                    if event.is_resp():
                        aio.create_task(self.resp_dispatcher.dispatch(event))
                    elif event.is_meta():
                        aio.create_task(self.meta_dispatcher.dispatch(event))
                    else:
                        aio.create_task(self.common_dispatcher.dispatch(event))
                
                except wse.ConnectionClosedError:
                    self._logger.warning("cq 主动关闭了连接, 将自动清理资源后关闭")
                    sys.exit(0)
                except Exception as e:
                    self._logger.debug(traceback.format_exc())
                    self._logger.error(f"连接模块内部异常抛出：{e}，事件对象为：{event}")
        except aio.CancelledError:
            self._logger.debug("事件接收例程已停止")
        except wse.ConnectionClosedOK:
            pass