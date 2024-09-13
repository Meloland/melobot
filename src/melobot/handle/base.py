from typing import TYPE_CHECKING

from ..adapter.model import Event
from ..ctx import LoggerCtx
from ..log.base import LogLevel
from ..typ import HandleLevel
from ..utils import RWContext
from .process import Flow

if TYPE_CHECKING:
    from ..plugin.base import Plugin


class EventHandler:
    def __init__(self, plugin: "Plugin", flow: Flow) -> None:
        self.flow = flow
        self.logger = LoggerCtx().get()
        self.name = flow.name

        self._plugin = plugin
        self._handle_ctrl = RWContext()
        self._temp = flow.temp
        self.invalid = False

    @property
    def priority(self) -> HandleLevel:
        return self.flow.priority

    async def _handle_event(self, event: Event) -> None:
        try:
            await self.flow.run(event)
        except Exception:
            self.logger.error(f"事件处理 {self.name} 发生异常")
            self.logger.exception(f"事件处理 {self.name} 发生异常")
            self.logger.generic_obj(
                f"异常点 event {event.id}", event.__dict__, level=LogLevel.ERROR
            )
            self.logger.generic_obj("异常点局部变量：", locals(), level=LogLevel.ERROR)

    async def handle(self, event: Event) -> None:
        if self.invalid:
            return

        if not self._temp:
            async with self._handle_ctrl.read():
                if self.invalid:
                    return
                return await self._handle_event(event)

        async with self._handle_ctrl.write():
            if self.invalid:
                return
            await self._handle_event(event)
            self.invalid = True
            return

    async def reset_prior(self, new_prior: HandleLevel) -> None:
        async with self._handle_ctrl.write():
            self.flow.priority = new_prior

    async def expire(self) -> None:
        async with self._handle_ctrl.write():
            self.invalid = True
