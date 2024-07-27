from ..adapter import Event_T
from ..session.option import AbstractRule, SessionOption
from ..session.base import BotSession
from ..exceptions import BotValueError
from ..log import BotLogger, LogLevel
from ..typing import Generic, HandleLevel
from ..utils import RWContext
from .base import ProcessFlow


class EventHandler(Generic[Event_T]):
    def __init__(
        self,
        name: str,
        etype: type[Event_T],
        flow: ProcessFlow,
        logger: BotLogger,
        priority: HandleLevel = HandleLevel.NORMAL,
        temp: bool = False,
        option: SessionOption[Event_T] | None = None,
    ) -> None:
        super().__init__()
        self.name = name
        self.etype = etype
        self.flow = flow
        self.logger = logger
        self.priority = priority

        self._handle_ctrl = RWContext()
        self._temp = temp
        self._invalid = False

        self._rule: AbstractRule[Event_T] | None
        if option is None:
            self._rule = None
            self._keep = False
            self._nowait_cb = None
            self._wait = True
        else:
            self._rule = option.rule
            self._keep = option.keep
            self._nowait_cb = option.nowait_cb
            self._wait = option.wait

        if self._wait and self._nowait_cb:
            self.logger.warning(
                f"{self.name} 会话选项“冲突等待”为 True 时，“冲突回调”永远不会被调用"
            )

    def __format__(self, format_spec: str) -> str:
        match format_spec:
            case "hexid":
                return f"{id(self):#x}"
            case _:
                raise BotValueError(f"未知的 EventHandler 格式化标识符：{format_spec}")

    async def _handle_event(self, event: Event_T) -> None:
        try:
            session = await BotSession[Event_T].get(
                event,
                rule=self._rule,
                wait=self._wait,
                nowait_cb=self._nowait_cb,
                keep=self._keep,
            )
            if session is None:
                return

            async with session.ctx():
                return await self.flow.run()

        except Exception:
            self.logger.error(f"事件处理 {self.name} 发生异常")
            self.logger.obj(
                event.__dict__, f"异常点 event {event.id}", level=LogLevel.ERROR
            )
            self.logger.exc(locals=locals())

    async def _handle(self, event: Event_T) -> None:
        if self._invalid:
            return

        if not isinstance(event, self.etype):
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

    async def _reset_prior(self, new_prior: HandleLevel) -> None:
        async with self._handle_ctrl.write():
            self.priority = new_prior

    async def _expire(self) -> None:
        async with self._handle_ctrl.write():
            self._invalid = True
