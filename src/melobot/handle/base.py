from typing import TYPE_CHECKING

from .._ctx import get_logger
from ..adapter.model import Event
from ..log.base import LogLevel
from ..session.base import Session
from ..typ import AsyncCallable, HandleLevel
from ..utils import RWContext
from .process import Flow

if TYPE_CHECKING:
    from ..plugin.base import Plugin


class EventHandler:
    def __init__(self, plugin: "Plugin", flow: Flow) -> None:
        self.flow = flow
        self.logger = get_logger()
        self.name = flow.name

        self._plugin = plugin
        self._handle_ctrl = RWContext()
        self._temp = flow.temp
        self.invalid = False

        if self.flow.option.wait and self.flow.option.nowait_cb:
            self.logger.warning(
                f"{self.name} 会话选项“冲突等待”为 True 时，“冲突回调”永远不会被调用"
            )

    @property
    def priority(self) -> HandleLevel:
        return self.flow.priority

    async def _run_flow(
        self,
        session_getter: AsyncCallable[[], Session | None],
        event: Event,
        flow: Flow,
    ) -> tuple[bool, Session | None]:
        status, pre_session = True, None

        if flow.pre_flow is not None:
            p_flow = flow.pre_flow
            status, pre_session = await self._run_flow(
                lambda: Session.get(
                    event,
                    rule=p_flow.option.rule,
                    wait=p_flow.option.wait,
                    nowait_cb=p_flow.option.nowait_cb,
                    keep=p_flow.option.keep,
                ),
                event,
                p_flow,
            )
        if not status:
            return False, None

        session = await session_getter()
        if session is None:
            return False, None
        if pre_session is not None:
            session << pre_session  # pylint: disable=pointless-statement

        async with session.ctx():
            status = await flow.run()
            return status, session

    async def _handle_event(self, event: Event) -> None:
        try:
            await self._run_flow(
                lambda: Session.get(
                    event,
                    rule=self.flow.option.rule,
                    wait=self.flow.option.wait,
                    nowait_cb=self.flow.option.nowait_cb,
                    keep=self.flow.option.keep,
                ),
                event,
                self.flow,
            )
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
