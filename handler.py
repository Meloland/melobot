import asyncio as aio
import traceback
from asyncio import Queue
from utils.Definition import *
from utils.Event import *
from utils.Store import BOT_STORE
from utils.Logger import BOT_LOGGER
from utils.Processor import EventProcesser


class BotHandler:
    """
    bot 事件、行为队列管理模块。
    内部某些异步方法（协程）作为任务会创建多个副本，以实现更好的异步性能。
    而在整个项目中，这些副本也被称作 “调度器”。
    负责对事件处理工作的调度
    """
    def __init__(self, action_queue: Queue, event_queue: Queue, \
                prior_action_queue: Queue, prior_event_queue: Queue) -> None:
        super().__init__()
        self.action_q = action_queue
        self.event_q = event_queue
        self.prior_action_q = prior_action_queue
        self.prior_event_q = prior_event_queue
        self.e_manager = EventProcesser()
    
    async def get_event(self, name) -> None:
        """
        监控 event 队列，交给 eventProcesser 处理
        """
        try:
            while True:
                try:
                    event: BotEvent = await self.event_q.get()
                    actions = await self.e_manager.handle(event)
                    if actions == []: continue
                    for action in actions:
                        t = aio.create_task(self.put_action(action))
                        await aio.wait_for(t, timeout=BOT_STORE['kernel']['KERNEL_TIMEOUT'])
                        BOT_LOGGER.info(
                            f"命令 {action['cmd_name']} {' | '.join(action['cmd_args'])} 执行成功√"
                        )
                except aio.TimeoutError:
                    pass
                except BotUnknownEvent:
                    BOT_LOGGER.warning(f'出现 bot 未知事件：{event.raw}')
                except Exception as e:
                    BOT_LOGGER.debug(traceback.format_exc())
                    BOT_LOGGER.error(f'内部发生预期外的异常：{e}，事件为：{event.raw}（bot 仍在运行）')
        except aio.CancelledError:
                BOT_LOGGER.debug(f'handler.get_event {name} 已被卸载')

    # TODO: action 未来重写部分
    async def put_action(self, action: dict) -> None:
        """
        放置指定的 action 到 action 队列
        """
        try:
            if self.action_q.full():
                BOT_LOGGER.warning("行为队列已满！短时间可能无法对任务回应")
            await self.action_q.put(action)
        except aio.CancelledError:
            BOT_LOGGER.debug('行为放置因超时而被取消')
    
    async def get_prior_event(self, name: str) -> None:
        """
        监控优先 event 队列，并交给 eventProcesser 处理
        """
        try:
            while True:
                try:
                    prior_event: BotEvent = await self.prior_event_q.get()
                    prior_actions = await self.e_manager.handle(prior_event)
                    if prior_actions == []: continue
                    for prior_action in prior_actions:
                        t = aio.create_task(self.put_prior_action(prior_action))
                        await aio.wait_for(t, timeout=BOT_STORE['kernel']['KERNEL_TIMEOUT'])
                        # TODO: action 未来重写部分
                        BOT_LOGGER.info(
                            f"命令 {prior_action['cmd_name']} {' | '.join(prior_action['cmd_args'])} 执行成功√"
                        )
                except aio.TimeoutError:
                    pass
                except BotUnknownEvent:
                    BOT_LOGGER.warning(f'出现 bot 未知事件：{prior_event.raw}')
                except Exception as e:
                    BOT_LOGGER.debug(traceback.format_exc())
                    BOT_LOGGER.error(f'内部发生预期外的异常：{e}，优先事件对象为：{prior_event.raw}（bot 仍在运行）')
        except aio.CancelledError:
            BOT_LOGGER.debug(f'handler.get_prior_event {name} 已被卸载')
        
    # TODO: action 未来重写部分
    async def put_prior_action(self, prior_action: dict) -> None:
        """
        放置指定的优先 action 到 优先 action 队列
        """
        try:
            if self.prior_action_q.full():
                BOT_LOGGER.warning("优先行为队列已满！短时间内可能无法产生优先行为")
            await self.prior_action_q.put(prior_action)
        except aio.CancelledError:
            BOT_LOGGER.debug('优先行为放置因超时而被取消')
    

    def coro_getter(self) -> None:
        """
        返回 handler 所有核心的异步协程给主模块，
        多开一些协程，以尽可能实现对大量事件的异步响应。
        """
        num = BOT_STORE['kernel']['EVENT_HANDLER_NUM']
        coro_list = []
        for i in range(int(num)):
            coro_list.append(self.get_event(name=f"h{i+1}"))
        for j in range(int(num/4)):
            coro_list.append(self.get_prior_event(name=f"ph{j+1}"))
        return coro_list
