from __future__ import annotations

import asyncio
from asyncio import Condition, Lock
from contextlib import _AsyncGeneratorContextManager, asynccontextmanager
from typing import Any, AsyncGenerator, cast

from ..adapter.model import Event
from ..ctx import FlowCtx, SessionCtx
from ..exceptions import BotException
from ..handle.process import stop
from ..typ import AsyncCallable
from .option import Rule

_SESSION_CTX = SessionCtx()


class SessionStateError(BotException):
    def __init__(self, meth: str | None = None, text: str | None = None) -> None:
        if text is not None:
            super().__init__(text)
            return

        super().__init__(f"当前会话状态不支持的操作：{meth}")


class SessionState:
    def __init__(self, session: "Session") -> None:
        self.session = session

    async def work(self, event: Event) -> None:
        raise SessionStateError(meth=SessionState.work.__name__)

    async def rest(self) -> None:
        raise SessionStateError(meth=SessionState.rest.__name__)

    async def suspend(self, timeout: float | None) -> bool:
        raise SessionStateError(meth=SessionState.suspend.__name__)

    async def wakeup(self, event: Event) -> None:
        raise SessionStateError(meth=SessionState.wakeup.__name__)

    async def expire(self) -> None:
        raise SessionStateError(meth=SessionState.expire.__name__)


class SpareSessionState(SessionState):
    async def work(self, event: Event) -> None:
        self.session.event = event
        self.session.to_state(WorkingSessionState)


class WorkingSessionState(SessionState):
    async def rest(self) -> None:
        if self.session.rule is None:
            raise SessionStateError(text="缺少会话规则，会话无法从“运行态”转为“空闲态”")

        cond = self.session.refresh_cond
        async with cond:
            cond.notify()
        self.session.to_state(SpareSessionState)

    async def suspend(self, timeout: float | None) -> bool:
        if self.session.rule is None:
            raise SessionStateError(text="缺少会话规则，会话无法从“运行态”转为“挂起态”")

        cond = self.session.refresh_cond
        async with cond:
            cond.notify()
        self.session.to_state(SuspendSessionState)

        async with self.session.wakeup_cond:
            if timeout is None:
                await self.session.wakeup_cond.wait()
                return True
            try:
                await asyncio.wait_for(self.session.wakeup_cond.wait(), timeout=timeout)
                return True
            except asyncio.TimeoutError:
                return False

    async def expire(self) -> None:
        if self.session.rule is not None:
            cond = self.session.refresh_cond
            async with cond:
                cond.notify()
        self.session.to_state(ExpireSessionState)


class SuspendSessionState(SessionState):

    async def wakeup(self, event: Event) -> None:
        self.session.event = event
        cond = self.session.wakeup_cond
        async with cond:
            cond.notify()
        self.session.to_state(WorkingSessionState)


class ExpireSessionState(SessionState): ...


class SessionStore(dict[str, Any]):
    """会话存储，生命周期伴随会话对象"""


class Session:
    """会话

    :ivar SessionStore store: 当前会话上下文的会话存储
    :ivar Rule rule: 当前会话上下文的会话规则
    """

    __instances__: dict[Rule, set["Session"]] = {}
    __instance_locks__: dict[Rule, Lock] = {}
    __cls_lock__ = Lock()

    def __init__(self, event: Event, rule: Rule | None, keep: bool = False) -> None:
        self.store: SessionStore = SessionStore()
        self.event = event
        self.rule = rule
        self.refresh_cond = Condition()
        self.wakeup_cond = Condition()
        self.keep = keep

        self._state: SessionState = WorkingSessionState(self)

    def to_state(self, state_class: type[SessionState]) -> None:
        self._state = state_class(self)

    def on_state(self, state_class: type[SessionState]) -> bool:
        return isinstance(self._state, state_class)

    async def work(self, event: Event) -> None:
        await self._state.work(event)

    async def rest(self) -> None:
        await self._state.rest()

    async def suspend(self, timeout: float | None = None) -> bool:
        return await self._state.suspend(timeout)

    async def wakeup(self, event: Event) -> None:
        await self._state.wakeup(event)

    async def expire(self) -> None:
        await self._state.expire()

    @classmethod
    async def get(
        cls,
        event: Event,
        rule: Rule | None = None,
        wait: bool = True,
        nowait_cb: AsyncCallable[[], None] | None = None,
        keep: bool = False,
    ) -> Session | None:
        if rule is None:
            return Session(event, rule=None, keep=keep)

        async with cls.__cls_lock__:
            cls.__instance_locks__.setdefault(rule, Lock())

        async with cls.__instance_locks__[rule]:
            _set = cls.__instances__.setdefault(rule, set())

            suspends = filter(lambda s: s.on_state(SuspendSessionState), _set)
            for session in suspends:
                if await rule.compare(session.event, event):
                    await session.wakeup(event)
                    return None

            spares = filter(lambda s: s.on_state(SpareSessionState), _set)
            for session in spares:
                if await rule.compare(session.event, event):
                    await session.work(event)
                    session.keep = keep
                    return session

            workings = filter(lambda s: s.on_state(WorkingSessionState), _set)
            expires = list(filter(lambda s: s.on_state(ExpireSessionState), _set))
            for session in workings:
                if not await rule.compare(session.event, event):
                    continue

                if not wait:
                    if nowait_cb is not None:
                        await nowait_cb()
                    return None

                cond = session.refresh_cond
                async with cond:
                    await cond.wait()
                    if session.on_state(ExpireSessionState):
                        expires.append(session)
                    elif session.on_state(SuspendSessionState):
                        await session.wakeup(event)
                        return None
                    else:
                        await session.work(event)
                        session.keep = keep
                        return session

            for session in expires:
                Session.__instances__[cast(Rule, session.rule)].remove(session)

            session = Session(event, rule=rule, keep=keep)
            Session.__instances__[rule].add(session)
            return session

    @classmethod
    @asynccontextmanager
    async def enter_ctx(
        cls,
        rule: Rule,
        wait: bool = True,
        nowait_cb: AsyncCallable[[], None] | None = None,
        keep: bool = False,
    ) -> AsyncGenerator[Session, None]:
        session = await cls.get(
            FlowCtx().get_event(),
            rule=rule,
            wait=wait,
            nowait_cb=nowait_cb,
            keep=keep,
        )
        if session is None:
            await stop()

        with _SESSION_CTX.in_ctx(session):
            try:
                yield session
            except asyncio.CancelledError:
                if session.on_state(SuspendSessionState):
                    await session.wakeup(session.event)
            finally:
                if session.keep:
                    await session.rest()
                else:
                    await session.expire()


async def suspend(timeout: float | None = None) -> bool:
    """挂起当前会话

    :param timeout: 挂起后再唤醒的超时时间, 为空则永不超时
    :return: 如果为 `False` 则表明唤醒超时
    """
    return await SessionCtx().get().suspend(timeout)


def enter_session(
    rule: Rule,
    wait: bool = True,
    nowait_cb: AsyncCallable[[], None] | None = None,
    keep: bool = False,
) -> _AsyncGeneratorContextManager[Session]:
    """上下文管理器，提供一个会话上下文，在此上下文中可使用会话的高级特性

    :param rule: 会话规则
    :param wait: 当出现会话冲突时，是否需要等待
    :param nowait_cb: 指定了 `wait=False` 后，会话冲突时执行的回调
    :param keep: 会话在退出会话上下文后是否继续保持
    :yield: 会话对象
    """
    return Session.enter_ctx(rule, wait, nowait_cb, keep)
