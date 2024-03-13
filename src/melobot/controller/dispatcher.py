import asyncio as aio

from ..types.abc import AbstractDispatcher
from ..types.exceptions import *
from ..types.tools import get_rich_str
from ..types.typing import *

if TYPE_CHECKING:
    from ..context.session import BotSessionManager
    from ..plugin.bot import BotHookBus
    from ..plugin.handler import EventHandler
    from ..types.abc import BotEvent
    from ..utils.logger import Logger


class BotDispatcher(AbstractDispatcher):
    """
    bot 分发模块。负责将传递的事件分发到各事件通道
    （接收的事件类型：消息、请求、通知和元事件）
    """

    def __init__(
        self,
        channel_map: dict[str, tuple[Type["EventHandler"], ...]],
        bot_bus: Type["BotHookBus"],
        ctx_manager: Type["BotSessionManager"],
        logger: "Logger",
    ) -> None:
        super().__init__()
        self.handlers: Dict[Type["EventHandler"], List["EventHandler"]] = {}

        self.logger = logger
        self._channel_map = channel_map
        self._bot_bus = bot_bus
        self._ctx_managger = ctx_manager
        self._ready_signal = aio.Event()

        for tuple in self._channel_map.values():
            for channel in tuple:
                if channel not in self.handlers.keys():
                    self.handlers[channel] = []

    def add_handlers(self, all_handlers: List["EventHandler"]) -> None:
        """
        绑定事件处理器列表
        """
        for handler in all_handlers:
            self.handlers[handler.__class__].append(handler)
        for k in self.handlers.keys():
            self.handlers[k] = sorted(
                self.handlers[k], key=lambda x: x.priority, reverse=True
            )
        self._ready_signal.set()

    async def broadcast(self, event: "BotEvent", channel: Type["EventHandler"]) -> None:
        """
        向指定的通道推送事件
        """
        try:
            permit_priority = PriorLevel.MIN.value
            handlers = self.handlers[channel]
            for handler in handlers:
                # 事件处理器优先级不够，则不分配给它处理
                if handler.priority < permit_priority:
                    continue
                if handler._direct_rouse and (
                    await self._ctx_managger.try_attach(event, handler)
                ):
                    if handler.set_block and handler.priority > permit_priority:
                        permit_priority = handler.priority
                    continue
                # evoke 返回的值用于判断，事件处理器内部经过各种检查后，是否选择处理这个事件。
                if not (await handler.evoke(event)):
                    # 如果决定不处理，则会跳过此次循环（也就是不进行“可能存在的优先级阻断操作”）
                    continue
                if handler.set_block and handler.priority > permit_priority:
                    permit_priority = handler.priority
        except Exception as e:
            self.logger.error(f"bot dispatcher 抛出异常")
            self.logger.error("异常点 event：\n" + get_rich_str(event))
            self.logger.error("异常回溯栈：\n" + get_better_exc(e))
            self.logger.error("异常点局部变量：\n" + get_rich_str(locals()))

    async def dispatch(self, event: "BotEvent") -> None:
        """
        把事件分发到对应的事件通道
        """
        await self._ready_signal.wait()
        await self._bot_bus.emit(BotLife.EVENT_BUILT, event, wait=True)
        self.logger.debug(f"event {id(event)} built hook 已完成")
        for channel in self._channel_map[event.type]:
            self.logger.debug(f"向 {channel.__name__} 通道广播 event {id(event)}")
            aio.create_task(self.broadcast(event, channel))
