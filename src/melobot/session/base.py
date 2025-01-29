from __future__ import annotations

import asyncio
from asyncio import Condition, Lock
from contextlib import _AsyncGeneratorContextManager, asynccontextmanager

from typing_extensions import Any, AsyncGenerator

from ..adapter.model import Event
from ..ctx import FlowCtx, SessionCtx
from ..exceptions import BotException
from ..handle.process import stop
from ..typ import AsyncCallable
from .option import CompareInfo, Rule

_SESSION_CTX = SessionCtx()


class SessionError(BotException): ...


class SessionStateFailed(SessionError):
    def __init__(self, cur_state: str, meth: str) -> None:
        self.cur_state = cur_state
        super().__init__(f"当前会话状态 {cur_state} 不支持的操作：{meth}")


class SessionRuleLacked(SessionError): ...


class SessionState:
    def __init__(self, session: "Session") -> None:
        self.session = session

    async def work(self, event: Event) -> None:
        raise SessionStateFailed(self.__class__.__name__, SessionState.work.__name__)

    async def rest(self) -> None:
        raise SessionStateFailed(self.__class__.__name__, SessionState.rest.__name__)

    async def suspend(self, timeout: float | None) -> bool:
        raise SessionStateFailed(self.__class__.__name__, SessionState.suspend.__name__)

    async def wakeup(self, event: Event) -> None:
        raise SessionStateFailed(self.__class__.__name__, SessionState.wakeup.__name__)

    async def expire(self) -> None:
        raise SessionStateFailed(self.__class__.__name__, SessionState.expire.__name__)


class SpareSessionState(SessionState):
    async def work(self, event: Event) -> None:
        self.session.event = event
        self.session.__to_state__(WorkingSessionState)


class WorkingSessionState(SessionState):
    async def rest(self) -> None:
        if self.session.rule is None:
            raise SessionRuleLacked("缺少会话规则，会话无法从“运行态”转为“空闲态”")

        cond = self.session.refresh_cond
        self.session.__to_state__(SpareSessionState)
        async with cond:
            cond.notify()

    async def suspend(self, timeout: float | None) -> bool:
        if self.session.rule is None:
            raise SessionRuleLacked("缺少会话规则，会话无法从“运行态”转为“挂起态”")

        cond = self.session.refresh_cond
        self.session.__to_state__(SuspendSessionState)
        async with cond:
            cond.notify()

        async with self.session.wakeup_cond:
            if timeout is None:
                await self.session.wakeup_cond.wait()
                return True

            try:
                await asyncio.wait_for(self.session.wakeup_cond.wait(), timeout=timeout)
                return True

            except asyncio.TimeoutError:
                if self.session.is_state(WorkingSessionState):
                    return True
                self.session.__to_state__(WorkingSessionState)
                return False

    async def expire(self) -> None:
        self.session.__to_state__(ExpireSessionState)
        if self.session.rule is not None:
            cond = self.session.refresh_cond
            async with cond:
                cond.notify()


class SuspendSessionState(SessionState):

    async def wakeup(self, event: Event) -> None:
        if self.session.is_state(WorkingSessionState):
            return
        self.session.event = event
        cond = self.session.wakeup_cond
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

    def __init__(self, event: Event, rule: Rule | None, keep: bool = False) -> None:
        self.store: SessionStore = SessionStore()
        self.event = event
        self.rule = rule
        self.refresh_cond = Condition()
        self.wakeup_cond = Condition()
        self.keep = keep

        self._state: SessionState = WorkingSessionState(self)

    def __to_state__(self, state_class: type[SessionState]) -> None:
        self._state = state_class(self)

    def is_state(self, state_class: type[SessionState]) -> bool:
        return isinstance(self._state, state_class)

    def mark_expire(self) -> None:
        self.keep = False

    async def __work__(self, event: Event) -> None:
        await self._state.work(event)

    async def __rest__(self) -> None:
        await self._state.rest()

    async def __suspend__(self, timeout: float | None = None) -> bool:
        return await self._state.suspend(timeout)

    async def __wakeup__(self, event: Event) -> None:
        await self._state.wakeup(event)

    async def __expire__(self) -> None:
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
            try:
                _set = cls.__instances__.setdefault(rule, set())

                suspends = filter(lambda s: s.is_state(SuspendSessionState), _set)
                for session in suspends:
                    if await rule.compare_with(
                        CompareInfo(session, session.event, event)
                    ):
                        await session.__wakeup__(event)
                        return None

                spares = filter(lambda s: s.is_state(SpareSessionState), _set)
                for session in spares:
                    if await rule.compare_with(
                        CompareInfo(session, session.event, event)
                    ):
                        await session.__work__(event)
                        session.keep = keep
                        return session

                workings = filter(lambda s: s.is_state(WorkingSessionState), _set)
                for session in workings:
                    if not await rule.compare_with(
                        CompareInfo(session, session.event, event)
                    ):
                        continue

                    if not wait:
                        if nowait_cb is not None:
                            await nowait_cb()
                        return None

                    cond = session.refresh_cond
                    async with cond:
                        await cond.wait()

                        if session.is_state(ExpireSessionState):
                            pass

                        elif session.is_state(SuspendSessionState):
                            await session.__wakeup__(event)
                            return None

                        else:
                            await session.__work__(event)
                            session.keep = keep
                            return session

                session = Session(event, rule=rule, keep=keep)
                Session.__instances__[rule].add(session)
                return session

            finally:
                expires = tuple(filter(lambda s: s.is_state(ExpireSessionState), _set))
                for session in expires:
                    Session.__instances__[rule].remove(session)

    @classmethod
    @asynccontextmanager
    async def enter(
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

        with _SESSION_CTX.unfold(session):
            try:
                yield session
            except asyncio.CancelledError:
                if session.is_state(SuspendSessionState):
                    await session.__wakeup__(session.event)
            finally:
                if session.keep:
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
    return Session.enter(rule, wait, nowait_cb, keep)
