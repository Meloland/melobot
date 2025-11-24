from __future__ import annotations

import asyncio
import inspect
from asyncio import Condition, Lock
from contextlib import _AsyncGeneratorContextManager, asynccontextmanager

from typing_extensions import Any, AsyncGenerator, Hashable

from ..adapter.model import Event
from ..ctx import FlowCtx, SessionCtx
from ..di import Depends
from ..exceptions import SessionError, SessionRuleLacked, SessionStateFailed
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
        if self.session.auto_release:
            self.session.release()
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
        self.session.release()


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


class SessionStore(dict[Hashable, Any]):
    """会话存储，生命周期伴随会话对象"""

    def set(self, key: Hashable, value: Any) -> None:
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
        auto_release: bool = True,
    ) -> None:
        self.store: SessionStore = SessionStore()
        self.event = first_completion.event
        self.rule = rule
        self.auto_release = auto_release

        self._completions: set[EventCompletion] = set()
        self._completions.add(first_completion)
        self._refresh_cond = Condition()
        self._wakeup_cond = Condition()
        self._keep = keep
        self._state: SessionState = WorkingSessionState(self)

    def stop_keep(self) -> None:
        """停止会话保持

        当进入会话时，启用了 `keep=True`，
        需要在会话不需要保持后，手动调用此方法标识会话可以销毁
        """
        self._keep = False

    def release(self, *events: Event) -> None:
        """释放对会话中事件的控制。允许它们参与“传播评估”。

        事件是否可以向更低优先级传播，需要在同级的所有处理流完成后进行评估。同级所有处理流完成后，
        如果事件为“不可传播”状态（event.spread = False），则不会向更低优先级传播。

        而会话必须存在于一个正在运行的处理流程中。对于会话中的事件，存在两种情况：

        1. 事件在会话挂起后，实际上就不再被需要（会话期待一个新的事件来继续处理流程）。
        那么挂起后，事件就应该允许参与传播评估。
        2. 事件在会话挂起后，仍然可能被需要（会话在下一阶段，仍然需要这个事件的信息）。
        那么挂起后，事件还不应该参与传播评估。

        melobot 将第一种情景视为默认情况（即使用 :func:`enter_session` 时，`auto_release=True`），
        此时每次挂起后，自动调用此方法释放对于事件的控制，允许它们参与传播评估。值得注意的是，此方法意为“释放”，
        传播评估**需要在当前事件的处理流程结束之后才会进行**。

        如果设置了 `auto_release=False`，则在挂起后保留对于事件的控制，需要手动调用此方法。
        而设置了 `keep=True` 时，无论 `auto_release` 如何设置，都需要手动调用此方法。

        总结：**一般情况下无需使用此方法**。但如果启用了会话，且需要更精准地控制事件的传播时机，可以考虑使用此方法。

        :param events: 事件对象。如果不提供，则释放会话历史中所有未释放的事件
        """
        if len(events) == 0:
            for c in self._completions:
                if c.flow_ended:
                    c.completed.set_result(None)
                else:
                    c.ctrl_by_session = False
            self._completions.clear()
            return

        rm_comps: list[EventCompletion] = []
        given_events = set(events)
        matched_events = set()
        for c in self._completions:
            if c.event in events:
                rm_comps.append(c)
                matched_events.add(c.event)
        remained_events = given_events - matched_events
        if len(remained_events) > 0:
            raise SessionError(
                f"会话历史中不存在指定的事件，或这些事件已经标记完成：{remained_events!r}"
            )

        for c in rm_comps:
            if c.flow_ended:
                c.completed.set_result(None)
            else:
                c.ctrl_by_session = False
        self._completions = set(filter(lambda c: c not in rm_comps, self._completions))

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
        auto_release: bool = True,
    ) -> Session | None:
        completion.ctrl_by_session = True
        if rule is None:
            return Session(
                rule=None,
                first_completion=completion,
                keep=keep,
                auto_release=auto_release,
            )

        async with cls.__cls_lock__:
            cls.__instance_locks__.setdefault(rule, Lock())

        async with cls.__instance_locks__[rule]:
            try:
                _set = cls.__instances__.setdefault(rule, set())

                suspends = filter(lambda s: s.__is_state__(SuspendSessionState), _set)
                for session in suspends:
                    if await rule.compare_with(
                        CompareInfo(session, session.event, completion.event)
                    ):
                        await session.__wakeup__(completion)
                        return None

                spares = filter(lambda s: s.__is_state__(SpareSessionState), _set)
                for session in spares:
                    if await rule.compare_with(
                        CompareInfo(session, session.event, completion.event)
                    ):
                        await session.__work__(completion)
                        session._keep = keep
                        return session

                workings = filter(lambda s: s.__is_state__(WorkingSessionState), _set)
                for session in workings:
                    if not await rule.compare_with(
                        CompareInfo(session, session.event, completion.event)
                    ):
                        continue

                    if not wait:
                        if nowait_cb is not None:
                            ret = nowait_cb()
                            if inspect.isawaitable(ret):
                                await ret
                        if completion.flow_ended:
                            completion.completed.set_result(None)
                        else:
                            completion.ctrl_by_session = False
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
                    auto_release=auto_release,
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
        auto_release: bool = True,
    ) -> AsyncGenerator[Session, None]:
        if SessionCtx().try_get():
            raise SessionError("当前已在会话上下文中，无法进入新的会话上下文")

        flow_ctx = FlowCtx()
        completion = flow_ctx.get_completion()
        session = await cls.get(
            completion,
            rule=rule,
            wait=wait,
            nowait_cb=nowait_cb,
            keep=keep,
            auto_release=auto_release,
        )
        if session is None:
            await stop()

        with _SESSION_CTX.unfold(session):
            try:
                yield session
            except asyncio.CancelledError:
                if session.__is_state__(SuspendSessionState):
                    await session.__wakeup__(completion=None)
                raise
            finally:
                if session._keep:
                    await session.__rest__()
                else:
                    await session.__expire__()


async def suspend(timeout: float | None = None, auto_stop: bool = False) -> bool:
    """挂起当前会话

    :param timeout: 挂起后再唤醒的超时时间, 为空则永不超时
    :param auto_stop: 如果挂起超时，是否自动停止当前事件的处理流
    :return: 如果为 `False` 则表明唤醒超时
    """
    status = await _SESSION_CTX.get().__suspend__(timeout)
    if auto_stop and not status:
        await stop()
    return status


def enter_session(
    rule: Rule,
    wait: bool = True,
    nowait_cb: SyncOrAsyncCallable[[], None] | None = None,
    keep: bool = False,
    auto_release: bool = True,
) -> _AsyncGeneratorContextManager[Session]:
    """上下文管理器，提供一个会话上下文，在此上下文中可使用会话的高级特性

    :param rule: 会话规则
    :param wait: 当出现会话冲突时，是否需要等待
    :param nowait_cb: 指定了 `wait=False` 后，会话冲突时执行的回调
    :param keep: 会话在退出会话上下文后是否继续保持
    :param auto_release: 当前会话挂起后，事件是否自动释放。其他有关细节参考 :meth:`Session.release`
    :yield: 会话对象
    """
    return Session.enter(rule, wait, nowait_cb, keep, auto_release)


class SessionArgDepend(Depends):
    def __init__(self, arg_idx: Hashable) -> None:
        self.arg_idx = arg_idx
        super().__init__(self._getter)

    def _getter(self) -> Any:
        s_store = _SESSION_CTX.get_store()
        empty = object()
        val = s_store.get(self.arg_idx, empty)
        if val is empty:
            raise KeyError(f"会话存储中没有键为 {self.arg_idx!r} 的值")
        return val


def get_session_arg(arg_idx: Hashable) -> Any:
    """获取会话存储中的值

    :param arg_idx: 键索引
    :return: 对应的依赖项
    """
    return SessionArgDepend(arg_idx)
