from __future__ import annotations

import asyncio
from asyncio import Condition, Lock
from contextlib import asynccontextmanager
from contextvars import ContextVar, Token

from ..adapter.model import Event, Event_T
from ..exceptions import BotException, BotSessionError
from ..typing import Any, AsyncCallable, AsyncGenerator, Generic, Optional
from ..utils import singleton
from .option import AbstractRule


class SessionStateError(BotException):
    def __init__(self, meth: str | None = None, text: str | None = None) -> None:
        if text is not None:
            super().__init__(text)
            return

        s = "当前会话状态不支持此操作"
        if meth is not None:
            s += f": {meth}"
        super().__init__(s)


class SessionState:
    def __init__(self, session: "Session") -> None:
        self.session = session

    async def work(self, event: Event_T) -> None:
        raise SessionStateError(SessionState.work.__name__)

    async def rest(self) -> None:
        raise SessionStateError(SessionState.rest.__name__)

    async def suspend(self) -> None:
        raise SessionStateError(SessionState.suspend.__name__)

    async def wakeup(self, event: Event_T) -> None:
        raise SessionStateError(SessionState.wakeup.__name__)

    async def expire(self) -> None:
        raise SessionStateError(SessionState.expire.__name__)


class SpareSessionState(SessionState):
    def __init__(self, session: "Session") -> None:
        super().__init__(session)

    async def work(self, event: Event_T) -> None:
        self.session.event = event
        self.session._to_state(WorkingSessionState)


class WorkingSessionState(SessionState):
    def __init__(self, session: "Session") -> None:
        super().__init__(session)

    async def rest(self) -> None:
        if self.session._rule is None:
            raise SessionStateError(text="缺少会话规则，会话无法从“运行态”转为“空闲态”")

        cond = self.session._refresh_cond
        async with cond:
            cond.notify()
        self.session._to_state(SpareSessionState)

    async def suspend(self) -> None:
        if self.session._rule is None:
            raise SessionStateError(text="缺少会话规则，会话无法从“运行态”转为“挂起态”")

        cond = self.session._refresh_cond
        async with cond:
            cond.notify()
        self.session._to_state(SuspendSessionState)

    async def expire(self) -> None:
        if self.session._rule is not None:
            cond = self.session._refresh_cond
            async with cond:
                cond.notify()

        self.session._expire()
        self.session._to_state(ExpireSessionState)


class SuspendSessionState(SessionState):
    def __init__(self, session: "Session") -> None:
        super().__init__(session)

    async def wakeup(self, event: Event_T) -> None:
        self.session.event = event
        cond = self.session._wakeup_cond
        async with cond:
            cond.notify()
        self.session._to_state(WorkingSessionState)


class ExpireSessionState(SessionState):
    def __init__(self, session: "Session") -> None:
        super().__init__(session)


class Session(Generic[Event_T]):
    _sets: dict[AbstractRule, set["Session"]] = {}
    _locks: dict[AbstractRule, Lock] = {}

    def __init__(
        self, event: Event_T, rule: AbstractRule | None, keep: bool = False
    ) -> None:
        self.store: dict[str, Any] = {}
        self.event = event

        self._rule = rule
        self._state: SessionState = WorkingSessionState(self)
        self._refresh_cond = Condition()
        self._wakeup_cond = Condition()
        self._keep = keep

        if rule is not None:
            Session._sets.setdefault(rule, set()).add(self)

    def __lshift__(self, another: "Session") -> None:
        self.store.update(another.store)

    def _expire(self) -> None:
        self.store.clear()
        if self._rule is not None:
            Session._sets[self._rule].remove(self)

    def _to_state(self, state_class: type[SessionState]) -> None:
        self._state = state_class(self)

    def _on_state(self, state_class: type[SessionState]) -> bool:
        return isinstance(self._state, state_class)

    async def _work(self, event: Event_T) -> None:
        await self._state.work(event)

    async def rest(self) -> None:
        await self._state.rest()

    async def suspend(self, timeout: float | None = None) -> bool:
        await self._state.suspend()
        async with self._wakeup_cond:
            if timeout is None:
                await self._wakeup_cond.wait()
                return True
            try:
                await asyncio.wait_for(self._wakeup_cond.wait(), timeout=timeout)
                return True
            except asyncio.TimeoutError:
                return False

    async def _wakeup(self, event: Event_T) -> None:
        await self._state.wakeup(event)

    async def expire(self) -> None:
        await self._state.expire()

    @classmethod
    async def get(
        cls,
        event: Event_T,
        rule: AbstractRule | None = None,
        wait: bool = True,
        nowait_cb: AsyncCallable[[], None] | None = None,
        keep: bool = False,
    ) -> Session[Event_T] | None:
        if rule is None:
            return Session(event, rule=None, keep=keep)

        cls._locks.setdefault(rule, Lock())
        async with cls._locks[rule]:
            _set = cls._sets.setdefault(rule, set())

            suspends = filter(lambda s: s._on_state(SuspendSessionState), _set)
            for session in suspends:
                if await rule.compare(session.event, event):
                    await session._wakeup(event)
                    return None

            spares = filter(lambda s: s._on_state(SpareSessionState), _set)
            for session in spares:
                if await rule.compare(session.event, event):
                    await session._work(event)
                    session._keep = keep
                    return session

            workings = filter(lambda s: s._on_state(WorkingSessionState), _set)
            for session in workings:
                if not await rule.compare(session.event, event):
                    continue

                if not wait:
                    if nowait_cb is not None:
                        await nowait_cb()
                    return None

                cond = session._refresh_cond
                async with cond:
                    await cond.wait()
                    if session._on_state(ExpireSessionState):
                        pass
                    elif session._on_state(SuspendSessionState):
                        await session._wakeup(event)
                        return None
                    else:
                        await session._work(event)
                        session._keep = keep
                        return session

        return Session(event, rule=rule, keep=keep)

    @asynccontextmanager
    async def ctx(self) -> AsyncGenerator[Session[Event_T], None]:
        local = SessionLocal()
        try:
            token = local.add(self)
            yield self
        except asyncio.CancelledError:
            if self._on_state(SuspendSessionState):
                await self._wakeup(self.event)
        finally:
            local.remove(token)
            await self.rest() if self._keep else await self.expire()


@singleton
class SessionLocal:
    def __init__(self) -> None:
        object.__setattr__(self, "__storage__", ContextVar("session_ctx"))
        self.__storage__: ContextVar[Session]

    def get(self) -> Session:
        try:
            return self.__storage__.get()
        except LookupError:
            raise BotSessionError("此时不在活动的事件处理流中，无法获取会话信息")

    def try_get(self) -> Session | None:
        return self.__storage__.get(None)

    def try_get_event(self) -> Event | None:
        session = self.try_get()
        return session.event if session is not None else None

    def add(self, ctx: Session) -> Token:
        return self.__storage__.set(ctx)

    def remove(self, token: Token) -> None:
        self.__storage__.reset(token)
