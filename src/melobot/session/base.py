from __future__ import annotations

import asyncio
import inspect
from asyncio import Condition, Future, Lock
from contextlib import _AsyncGeneratorContextManager, asynccontextmanager

from typing_extensions import Any, AsyncGenerator

from ..adapter.model import Event
from ..ctx import FlowCtx, SessionCtx
from ..exceptions import SessionRuleLacked, SessionStateFailed
from ..handle.base import EventCompletion, stop
from ..typ.base import SyncOrAsyncCallable
from .option import CompareInfo, Rule

_SESSION_CTX = SessionCtx()


class SessionState:
    def __init__(self, session: "Session") -> None:
        self.session = session

    async def work(self, completion: EventCompletion) -> None:
        raise SessionStateFailed(self.__class__.__name__, SessionState.work.__name__)

    async def rest(self) -> None:
        raise SessionStateFailed(self.__class__.__name__, SessionState.rest.__name__)

    async def suspend(self, timeout: float | None) -> bool:
        raise SessionStateFailed(self.__class__.__name__, SessionState.suspend.__name__)

    async def wakeup(self, completion: EventCompletion | None) -> None:
        raise SessionStateFailed(self.__class__.__name__, SessionState.wakeup.__name__)

    async def expire(self) -> None:
        raise SessionStateFailed(self.__class__.__name__, SessionState.expire.__name__)


class SpareSessionState(SessionState):
    async def work(self, completion: EventCompletion) -> None:
        self.session._completions.add(completion)
        self.session.event = completion.event
        self.session.__to_state__(WorkingSessionState)


class WorkingSessionState(SessionState):
    async def rest(self) -> None:
        if self.session.rule is None:
            raise SessionRuleLacked("缺少会话规则，会话无法从“运行态”转为“空闲态”")

        cond = self.session._refresh_cond
        self.session.__to_state__(SpareSessionState)
        async with cond:
            cond.notify()

    async def suspend(self, timeout: float | None) -> bool:
        self.session.set_completed()

        if self.session.rule is None:
            raise SessionRuleLacked("缺少会话规则，会话无法从“运行态”转为“挂起态”")

        cond = self.session._refresh_cond
        self.session.__to_state__(SuspendSessionState)
        async with cond:
            cond.notify()

        async with self.session._wakeup_cond:
            if timeout is None:
                await self.session._wakeup_cond.wait()
                return True

            try:
                await asyncio.wait_for(self.session._wakeup_cond.wait(), timeout=timeout)
                return True

            except asyncio.TimeoutError:
                if self.session.__is_state__(WorkingSessionState):
                    return True
                self.session.__to_state__(WorkingSessionState)
                return False

    async def expire(self) -> None:
        self.session.__to_state__(ExpireSessionState)
        if self.session.rule is not None:
            cond = self.session._refresh_cond
            async with cond:
                cond.notify()

        self.session.set_completed()


class SuspendSessionState(SessionState):

    async def wakeup(self, completion: EventCompletion | None) -> None:
        if self.session.__is_state__(WorkingSessionState):
            return

        if completion is not None:
            self.session._completions.add(completion)
            self.session.event = completion.event
        cond = self.session._wakeup_cond
        self.session.__to_state__(WorkingSessionState)
        async with cond:
            cond.notify()


class ExpireSessionState(SessionState): ...


class SessionStore(dict[str, Any]):
    """会话存储，生命周期伴随会话对象"""

    def set(self, key: str, value: Any) -> None:
        self[key] = value


class Session:
    """会话

    :ivar SessionStore store: 当前会话上下文的会话存储
    :ivar Rule rule: 当前会话上下文的会话规则
    """

    __instances__: dict[Rule, set["Session"]] = {}
    __instance_locks__: dict[Rule, Lock] = {}
    __cls_lock__ = Lock()

    def __init__(
        self,
        rule: Rule | None,
        first_completion: EventCompletion,
        keep: bool = False,
        auto_complete: bool = True,
    ) -> None:
        self.store: SessionStore = SessionStore()
        self.event = first_completion.event
        self.rule = rule
        self.auto_complete = auto_complete

        self._completions: set[EventCompletion] = set()
        self._completions.add(first_completion)
        self._refresh_cond = Condition()
        self._wakeup_cond = Condition()
        self._keep = keep
        self._state: SessionState = WorkingSessionState(self)

    def stop_keep(self) -> None:
        self._keep = False

    def set_completed(self, event: Event | None = None) -> None:
        if event is None:
            for c in self._completions:
                c.completed.set_result(None)
            self._completions.clear()
            return

        comps = filter(lambda c: c.event is event, self._completions)
        for c in comps:
            c.completed.set_result(None)
            self._completions.remove(c)

    def get_incompletions(self) -> list[tuple[Event, Future]]:
        return [(c.event, c.completed) for c in self._completions if not c.completed.done()]

    def __to_state__(self, state_class: type[SessionState]) -> None:
        self._state = state_class(self)

    def __is_state__(self, state_class: type[SessionState]) -> bool:
        return isinstance(self._state, state_class)

    async def __work__(self, completion: EventCompletion) -> None:
        await self._state.work(completion)

    async def __rest__(self) -> None:
        await self._state.rest()

    async def __suspend__(self, timeout: float | None = None) -> bool:
        return await self._state.suspend(timeout)

    async def __wakeup__(self, completion: EventCompletion | None) -> None:
        await self._state.wakeup(completion)

    async def __expire__(self) -> None:
        await self._state.expire()

    @classmethod
    async def get(
        cls,
        completion: EventCompletion,
        rule: Rule | None = None,
        wait: bool = True,
        nowait_cb: SyncOrAsyncCallable[[], None] | None = None,
        keep: bool = False,
        auto_complete: bool = True,
    ) -> Session | None:
        event = completion.event
        if rule is None:
            return Session(
                rule=None,
                first_completion=completion,
                keep=keep,
                auto_complete=auto_complete,
            )

        async with cls.__cls_lock__:
            cls.__instance_locks__.setdefault(rule, Lock())

        async with cls.__instance_locks__[rule]:
            try:
                _set = cls.__instances__.setdefault(rule, set())

                suspends = filter(lambda s: s.__is_state__(SuspendSessionState), _set)
                for session in suspends:
                    if await rule.compare_with(CompareInfo(session, session.event, event)):
                        await session.__wakeup__(completion)
                        return None

                spares = filter(lambda s: s.__is_state__(SpareSessionState), _set)
                for session in spares:
                    if await rule.compare_with(CompareInfo(session, session.event, event)):
                        await session.__work__(completion)
                        session._keep = keep
                        return session

                workings = filter(lambda s: s.__is_state__(WorkingSessionState), _set)
                for session in workings:
                    if not await rule.compare_with(CompareInfo(session, session.event, event)):
                        continue

                    if not wait:
                        if nowait_cb is not None:
                            ret = nowait_cb()
                            if inspect.isawaitable(ret):
                                await ret
                        completion.completed.set_result(None)
                        return None

                    cond = session._refresh_cond
                    async with cond:
                        await cond.wait()

                        if session.__is_state__(ExpireSessionState):
                            pass

                        elif session.__is_state__(SuspendSessionState):
                            await session.__wakeup__(completion)
                            return None

                        else:
                            await session.__work__(completion)
                            session._keep = keep
                            return session

                session = Session(
                    rule=rule,
                    first_completion=completion,
                    keep=keep,
                    auto_complete=auto_complete,
                )
                Session.__instances__[rule].add(session)
                return session

            finally:
                expires = tuple(filter(lambda s: s.__is_state__(ExpireSessionState), _set))
                for session in expires:
                    Session.__instances__[rule].remove(session)

    @classmethod
    @asynccontextmanager
    async def enter(
        cls,
        rule: Rule,
        wait: bool = True,
        nowait_cb: SyncOrAsyncCallable[[], None] | None = None,
        keep: bool = False,
        auto_complete: bool = True,
    ) -> AsyncGenerator[Session, None]:
        flow_ctx = FlowCtx()
        completion = flow_ctx.get_completion()
        completion.under_session = True

        session = await cls.get(
            completion,
            rule=rule,
            wait=wait,
            nowait_cb=nowait_cb,
            keep=keep,
            auto_complete=auto_complete,
        )
        if session is None:
            await stop()

        with _SESSION_CTX.unfold(session):
            try:
                yield session
            except asyncio.CancelledError:
                if session.__is_state__(SuspendSessionState):
                    await session.__wakeup__(completion=None)
            finally:
                if session._keep:
                    await session.__rest__()
                else:
                    await session.__expire__()


async def suspend(timeout: float | None = None) -> bool:
    """挂起当前会话

    :param timeout: 挂起后再唤醒的超时时间, 为空则永不超时
    :return: 如果为 `False` 则表明唤醒超时
    """
    return await _SESSION_CTX.get().__suspend__(timeout)


def enter_session(
    rule: Rule,
    wait: bool = True,
    nowait_cb: SyncOrAsyncCallable[[], None] | None = None,
    keep: bool = False,
    auto_complete: bool = True,
) -> _AsyncGeneratorContextManager[Session]:
    """上下文管理器，提供一个会话上下文，在此上下文中可使用会话的高级特性

    :param rule: 会话规则
    :param wait: 当出现会话冲突时，是否需要等待
    :param nowait_cb: 指定了 `wait=False` 后，会话冲突时执行的回调
    :param keep: 会话在退出会话上下文后是否继续保持
    :param auto_complete: 当前会话挂起后，事件是否自动向更低优先级传播
    :yield: 会话对象
    """
    return Session.enter(rule, wait, nowait_cb, keep, auto_complete)
