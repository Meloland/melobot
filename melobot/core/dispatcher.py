import asyncio as aio

from ..interface.core import IEventDispatcher
from ..interface.plugins import *
from ..interface.typing import *
from ..models.event import BotEvent
from ..models.exceptions import *
from ..plugins.handler import *


class BotDispatcher(IEventDispatcher):
    """
    bot 调度模块。负责将传递进来的普通事件（送入各事件总线，
    总线上绑定的事件处理器会捕获并处理事件。
    （接收的事件类型：消息、请求和通知）
    """
    def __init__(self) -> None:
        super().__init__()
        self.handlers: Dict[str, List[IEventHandler]]

        self._ready_signal = aio.Event()
        self._locks: Dict[str, aio.Lock]

    def bind(self, msg_handlers: List[MsgEventHandler], req_handlers: List[ReqEventHandler], 
             notice_handlers: List[NoticeEventHandler]) -> None:
        """
        绑定事件处理器列表，列表应该是按优先级排序过的。
        """
        self.handlers = {
            'message': sorted(msg_handlers, key=lambda x:x.priority, reverse=True),
            'request': sorted(req_handlers, key=lambda x:x.priority, reverse=True),
            'notice': sorted(notice_handlers, key=lambda x:x.priority, reverse=True)
        }
        self._locks = {
            'message': aio.Lock(),
            'request': aio.Lock(),
            'notice': aio.Lock()
        }
        self._ready_signal.set()

    async def dispatch(self, event: BotEvent) -> None:
        await self._ready_signal.wait()

        async with self._locks[event.type]:
            permit_priority = PriorityLevel.MIN.value
            handlers = self.handlers[event.type]

            for handler in handlers:
                # 如果被高优先级的事件处理器阻断，或已经无效、或前置验证不通过，不予处理
                if handler.priority < permit_priority or not handler.is_valid or \
                    not handler.verify(event):
                    continue

                aio.create_task(handler.handle(event))
                # 一次性处理器一次处理后，更改有效标志
                if handler.is_temp:
                    handler.is_valid = False
                # 更高优先级，可以更新阻断级别
                if handler.set_block and handler.priority > permit_priority:
                    permit_priority = handler.priority
            
            self.handlers[event.type] = list(filter(lambda x: x.is_valid, handlers))
