import asyncio as aio
import traceback

from ..models.bot import BotHookBus
from ..models.event import BotEvent
from ..models.handler import (
    EventHandler,
    MetaEventHandler,
    MsgEventHandler,
    NoticeEventHandler,
    ReqEventHandler,
)
from ..types.core import AbstractDispatcher
from ..types.exceptions import *
from ..types.models import BotLife
from ..types.typing import *
from ..utils.logger import Logger


class BotDispatcher(AbstractDispatcher):
    """
    bot 调度模块。负责将传递的普通事件送入各事件总线
    （接收的事件类型：消息、请求和通知）
    """

    def __init__(self, logger: Logger) -> None:
        super().__init__()
        self._handlers: Dict[str, List[EventHandler]] = {
            "message": [],
            "request": [],
            "notice": [],
            "meta": [],
        }
        self.logger = logger

        self._ready_signal = aio.Event()

    def add_handlers(self, all_handlers: List[EventHandler]) -> None:
        """
        绑定事件处理器列表
        """
        self._ready_signal.clear()

        for handler in all_handlers:
            if isinstance(handler, MsgEventHandler):
                self._handlers["message"].append(handler)
            elif isinstance(handler, ReqEventHandler):
                self._handlers["request"].append(handler)
            elif isinstance(handler, NoticeEventHandler):
                self._handlers["notice"].append(handler)
            elif isinstance(handler, MetaEventHandler):
                self._handlers["meta"].append(handler)
        for k in self._handlers.keys():
            self._handlers[k] = sorted(
                self._handlers[k], key=lambda x: x.priority, reverse=True
            )

        self._ready_signal.set()

    async def dispatch(self, event: BotEvent) -> None:
        """
        把事件分发到对应的事件总线
        """
        await self._ready_signal.wait()
        await BotHookBus.emit(BotLife.EVENT_BUILT, event, wait=True)

        try:
            permit_priority = PriorLevel.MIN.value
            handlers = self._handlers[event.type]
            for handler in handlers:
                # 事件处理器优先级不够，则不分配给它处理
                if handler.priority < permit_priority:
                    continue
                # evoke 返回的值用于判断，事件处理器内部经过各种检查后，是否选择处理这个事件。
                if not (await handler.evoke(event)):
                    # 如果决定不处理，则会跳过此次循环（也就是不进行“可能存在的优先级阻断操作”）
                    continue
                if handler.set_block and handler.priority > permit_priority:
                    permit_priority = handler.priority
        except Exception as e:
            self.logger.error(f"bot dispatcher 抛出异常：[{e.__class__.__name__}] {e}")
            self.logger.debug(f"异常点的事件记录为：{event.raw}")
            self.logger.debug("异常回溯栈：\n" + traceback.format_exc().strip("\n"))
