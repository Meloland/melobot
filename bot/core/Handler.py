import asyncio as aio
from asyncio import Queue
from common.Typing import *
from common.Event import *
from common.Store import BOT_STORE
from common.Exceptions import *
from .Processor import EventProcesser


class BotHandler:
    """
    bot 调度器，从事件队列抽取事件交给事件处理器。
    """
    def __init__(self, event_queue: Queue, prior_event_queue: Queue, resp_queue: Queue) -> None:
        super().__init__()
        self.event_q = event_queue
        self.prior_event_q = prior_event_queue
        self.resp_q = resp_queue
        self.e_manager = EventProcesser()
    
    async def recv_event(self) -> None:
        """
        监控 event 队列，交给 eventProcesser 处理
        """
        try:
            await self.e_manager.build_executor()
            while True:
                event: BotEvent = await self.event_q.get()
                if event.is_resp():
                    await self.send_resp(event)
                    continue
                # 创建 task，但是此处不等待。超时和异常处理由内部 EventManager 完成
                aio.create_task(self.e_manager.handle(event))
        except aio.CancelledError:
                BOT_STORE.logger.debug(f'handler.recv_event 已被卸载')
    
    async def recv_prior_event(self) -> None:
        """
        监控优先 event 队列，并交给 eventProcesser 处理
        """
        try:
            await self.e_manager.build_executor()
            while True:
                prior_event: BotEvent = await self.prior_event_q.get()
                aio.create_task(self.e_manager.handle(prior_event))
        except aio.CancelledError:
            BOT_STORE.logger.debug(f'handler.recv_prior_event 已被卸载')

    async def send_resp(self, resp: RespEvent) -> None:
        """
        将 resp 事件提交至 resp 队列，供响应器使用
        """
        try:
            t = aio.create_task(self.resp_q.put(resp))
            await aio.wait_for(t, timeout=BOT_STORE.meta.kernel_timeout)
        except TimeoutError:
            BOT_STORE.logger.warning('事件队列已满！传递响应事件超时！')

    def coro_getter(self) -> List[Coroutine]:
        """
        返回 Handler 所有核心的异步协程
        """
        return [
            self.recv_event(),
            self.recv_prior_event()
        ]
