import asyncio as aio

from ..interface.core import IEventDispatcher
from ..interface.plugin import *
from ..interface.typing import *
from ..models.event import BotEvent
from ..models.exceptions import *
from ..core.plugin import MsgEventHandler, ReqEventHandler, NoticeEventHandler


class BotDispatcher(IEventDispatcher):
    """
    bot 调度模块。负责将传递进来的普通事件（送入各事件总线，
    总线上绑定的事件处理器会捕获并处理事件。
    （接收的事件类型：消息、请求和通知）
    """
    def __init__(self) -> None:
        super().__init__()
        self.handlers: Dict[str, List[IEventHandler]] = {
            'message': [],
            'request': [],
            'notice': []
        }

        self._ready_signal = aio.Event()

    def bind_handlers(self, all_handlers: List[IEventHandler]) -> None:
        """
        绑定事件处理器列表
        """
        for handler in all_handlers:
            if isinstance(handler, MsgEventHandler):
                self.handlers['message'].append(handler)
            elif isinstance(handler, ReqEventHandler):
                self.handlers['request'].append(handler)
            elif isinstance(handler, NoticeEventHandler):
                self.handlers['notice'].append(handler)

        for k in self.handlers.keys():
            self.handlers[k] = sorted(self.handlers[k], key=lambda x:x.priority, reverse=True)
        self._ready_signal.set()

    async def dispatch(self, event: BotEvent) -> None:
        await self._ready_signal.wait()

        permit_priority = PriorityLevel.MIN.value
        handlers = self.handlers[event.type]

        for handler in handlers:
            # 如果被高优先级的事件处理器阻断，不予处理
            if handler.priority < permit_priority:
                continue
            if not (await handler.evoke(event)):
                continue

            if handler.set_block and handler.priority > permit_priority:
                permit_priority = handler.priority
