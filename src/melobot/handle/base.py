from ..adapter.model import Event
from ..log import LogLevel, get_ctx_logger
from ..session.base import Session
from ..session.option import AbstractRule
from ..typing import TYPE_CHECKING, HandleLevel
from ..utils import RWContext
from .process import ProcessFlow

if TYPE_CHECKING:
    from ..plugin.base import Plugin


class EventHandler:
    def __init__(self, plugin: "Plugin", flow: ProcessFlow) -> None:
        self.flow = flow
        self.logger = get_ctx_logger()
        self.name = flow.name
        self.event_type = flow.event_type

        self._plugin = plugin
        self._handle_ctrl = RWContext()
        self._temp = flow.temp
        self._invalid = False

        self._rule: AbstractRule | None
        if flow.option is None:
            self._rule = None
            self._keep = False
            self._nowait_cb = None
            self._wait = True
        else:
            self._rule = flow.option.rule
            self._keep = flow.option.keep
            self._nowait_cb = flow.option.nowait_cb
            self._wait = flow.option.wait

        if self._wait and self._nowait_cb:
            self.logger.warning(
                f"{self.name} 会话选项“冲突等待”为 True 时，“冲突回调”永远不会被调用"
            )

    @property
    def priority(self) -> HandleLevel:
        return self.flow.priority

    async def _handle_event(self, event: Event) -> None:
        try:
            session = await Session.get(
                event,
                rule=self._rule,
                wait=self._wait,
                nowait_cb=self._nowait_cb,
                keep=self._keep,
            )
            if session is None:
                return

            async with session.ctx():
                return await self.flow._run()

        except Exception:
            self.logger.error(f"事件处理 {self.name} 发生异常")
            self.logger.obj(
                event.__dict__, f"异常点 event {event.id}", level=LogLevel.ERROR
            )
            self.logger.exc(locals=locals())

    async def handle(self, event: Event) -> None:
        if self._invalid:
            return

        if not isinstance(event, self.event_type):
            return

        if not self._temp:
            async with self._handle_ctrl.read():
                if self._invalid:
                    return
                return await self._handle_event(event)

        async with self._handle_ctrl.write():
            if self._invalid:
                return
            await self._handle_event(event)
            self._invalid = True
            return

    async def reset_prior(self, new_prior: HandleLevel) -> None:
        async with self._handle_ctrl.write():
            self.flow.priority = new_prior

    async def expire(self) -> None:
        async with self._handle_ctrl.write():
            self._invalid = True
