import asyncio as aio
import time
from contextvars import ContextVar, Token
from copy import deepcopy
from functools import wraps

from ..types.abc import SessionRule
from ..types.exceptions import *
from ..types.typing import *
from ..utils.atools import get_twin_event

if TYPE_CHECKING:
    from ..models.event import MessageEvent, MetaEvent, NoticeEvent, RequestEvent
    from ..types.abc import AbstractResponder, BotAction, BotEvent
    from ..plugin.handler import EventHandler


class BotSession:
    """
    Bot Session 类。不需要直接实例化，必须通过 BotSessionBuilder 构造。
    """

    def __init__(
        self,
        manager: Type["BotSessionManager"],
        responder: "AbstractResponder",
        space_tag: "EventHandler" = None,
    ) -> None:
        super().__init__()
        self.store = {}
        self.timestamp = time.time()
        self.hup_times: List[float] = []
        self.events: List[
            "MessageEvent" | "RequestEvent" | "MetaEvent" | "NoticeEvent"
        ] = []
        self.actions: List["BotAction"] = []

        self._manager = manager
        self._responder = responder
        # session 是否空闲的标志，由 BotSessionManager 修改和管理
        self._free_signal = aio.Event()
        self._free_signal.set()
        # session 是否挂起的标志。二者互为孪生反状态。由 BotSessionManager 修改和管理
        # 注意 session 挂起时一定是非空闲和非过期的
        self._hup_signal, self._awake_signal = get_twin_event()
        # session 是否过期的标志，由 BotSessionManager 修改和管理
        self._expired = False
        # 用于标记该 session 属于哪个 session 空间，如果为 None 则表明是空 session 或是一次性 session
        # 其实这里如果传入 space_tag 则一定是所属 handler 的引用
        self._space_tag: Optional["EventHandler"] = space_tag
        # 所属 handler 的引用（和 space_tag 不一样，所有在 handler 中产生的 session，此属性必为非空）
        self._handler: "EventHandler" = None

    @property
    def event(
        self,
    ) -> Union["MessageEvent", "RequestEvent", "MetaEvent", "NoticeEvent"]:
        try:
            return next(reversed(self.events))
        except StopIteration:
            raise BotSessionError("当前 session 下不存在可用的 event")

    @property
    def last_action(self) -> "BotAction":
        try:
            return next(reversed(self.actions))
        except StopIteration:
            raise BotSessionError("当前 session 下尚未进行过 action 操作")

    @property
    def last_hup(self) -> Optional[float]:
        try:
            return next(reversed(self.hup_times))
        except StopIteration:
            return None

    @property
    def args(self):
        if self._handler is not None and self.event._args_map is not None:
            args_group = self.event._args_map.get(self._handler.parser.id)
            if self._handler.parser.target is None:
                return deepcopy(args_group)
            for cmd_name in self._handler.parser.target:
                args = args_group.get(cmd_name)
                if args is not None:
                    return deepcopy(args.vals)
            raise BotSessionError("尝试获取的命令解析参数不存在")
        return None

    async def hup(self, overtime: int = None) -> None:
        """
        当前 session 挂起（也就是所在方法的挂起）。直到满足同一 session_rule 的事件重新进入，
        session 所在方法便会被唤醒。但如果设置了超时时间且在唤醒前超时，则会强制唤醒 session，
        并抛出 SessionHupTimeout 异常
        """
        self._manager._hup(self)
        if overtime is None:
            await self._awake_signal.wait()
        elif overtime <= 0:
            raise BotSessionError("session 挂起超时时间（秒数）必须 > 0")
        else:
            await aio.wait(
                [self._awake_signal.wait(), aio.sleep(overtime)],
                return_when=aio.FIRST_COMPLETED,
            )
            if self._awake_signal.is_set():
                return
            self._manager._rouse(self)
            raise SessionHupTimeout("session 挂起超时")

    def destory(self) -> None:
        """
        销毁方法。
        其他 session 调用会立即清空 session 存储、事件记录、挂起时间记录。
        如果调用 session 有 space_tag，还会从存储空间中移除该 session
        """
        if self.event is None:
            pass
        else:
            self._manager._expire(self)

    def store_get(self, key: Any) -> Any:
        return self.store[key]

    def store_add(self, key: Any, val: Any) -> None:
        self.store[key] = val

    def store_update(self, store: dict) -> None:
        self.store.update(store)

    def store_remove(self, key: Any) -> None:
        self.store.pop(key)

    def store_clear(self) -> None:
        self.store.clear()


class SessionLocal:
    """
    session 自动上下文
    """

    __slots__ = tuple(
        list(filter(lambda x: not (len(x) >= 2 and x[:2] == "__"), dir(BotSession)))
        + ["__storage__"]
    )

    def __init__(self) -> None:
        object.__setattr__(self, "__storage__", ContextVar("session_ctx"))
        self.__storage__: ContextVar[BotSession]

    def __setattr__(self, __name: str, __value: Any) -> None:
        setattr(self.__storage__.get(), __name, __value)

    def __getattr__(self, __name: str) -> Any:
        return getattr(self.__storage__.get(), __name)

    def _add_ctx(self, ctx: BotSession) -> Token:
        return self.__storage__.set(ctx)

    def _del_ctx(self, token: Token) -> None:
        self.__storage__.reset(token)


SESSION_LOCAL = SessionLocal()
SESSION_LOCAL: BotSession


class AttrSessionRule(SessionRule):
    def __init__(self, *attrs) -> None:
        super().__init__()
        self.attrs = attrs

    def _get_val(self, e: "BotEvent", attrs: Tuple[str, ...]) -> Any:
        val = e
        try:
            for attr in attrs:
                val = getattr(val, attr)
        except AttributeError:
            raise BotSessionError(f"session 规则指定的属性 {attr} 不存在")
        return val

    def compare(self, e1: "BotEvent", e2: "BotEvent") -> bool:
        return self._get_val(e1, self.attrs) == self._get_val(e2, self.attrs)


class BotSessionManager:
    STORAGE: Dict["EventHandler", Set[BotSession]] = {}
    HUP_STORAGE: Dict["EventHandler", Set[BotSession]] = {}
    # 各个 handler 对饮的操作锁
    WORK_LOCKS: Dict["EventHandler", aio.Lock] = {}
    # 用来标记 cls.get 等待一个挂起的 session 时的死锁
    DEADLOCK_FLAGS: Dict["EventHandler", aio.Event] = {}
    # 对应每个 handler 的 try_attach 过程的操作锁
    ATTACH_LOCKS: Dict["EventHandler", aio.Lock] = {}
    RESPONDER: "AbstractResponder"

    @classmethod
    def _bind(cls, responder: "AbstractResponder") -> None:
        cls.RESPONDER = responder

    @classmethod
    def register(cls, handler: "EventHandler") -> None:
        """
        以 handler 为键，注册 handler 对应的 session 空间、操作锁和挂起 session 空间
        """
        cls.STORAGE[handler] = set()
        cls.WORK_LOCKS[handler] = aio.Lock()
        cls.HUP_STORAGE[handler] = set()
        cls.DEADLOCK_FLAGS[handler] = aio.Event()
        cls.ATTACH_LOCKS[handler] = aio.Lock()

    @classmethod
    def inject(cls, session: BotSession, handler: "EventHandler") -> None:
        """
        handler 内绑定 handler 引用到 session
        """
        session._handler = handler

    @classmethod
    def _attach(cls, event: "BotEvent", handler: "EventHandler") -> bool:
        """
        session 附着操作，临界区操作。只能在 cls.try_attach 中进行
        """
        session = None
        for s in cls.HUP_STORAGE[handler]:
            # session 的挂起方法，保证 session 一定未过期，因此不进行过期检查
            if handler._rule.compare(s.event, event):
                session = s
                break
        # 如果获得一个挂起的 session，它一定是可附着的，附着后需要唤醒
        if session:
            session.events.append(event)
            cls._rouse(session)
            return True
        return False

    @classmethod
    async def try_attach(cls, event: "BotEvent", handler: "EventHandler") -> bool:
        """
        检查是否有挂起的 session 可供 event 附着。
        如果有则附着并唤醒，并返回 True。否则返回 False。
        """
        if handler._rule is None:
            return False

        async with cls.ATTACH_LOCKS[handler]:
            t1 = aio.create_task(cls.DEADLOCK_FLAGS[handler].wait(), name="flag")
            t2 = aio.create_task(cls.WORK_LOCKS[handler].acquire(), name="lock")
            done, _ = await aio.wait([t1, t2], return_when=aio.FIRST_COMPLETED)
            # 等待完成后，一定要记得取消另一个任务！否则可能异常加锁
            if done.pop().get_name() == "flag":
                res = cls._attach(event, handler)
                cls.DEADLOCK_FLAGS[handler].clear()
                t2.cancel()
                return res
            else:
                res = cls._attach(event, handler)
                cls.WORK_LOCKS[handler].release()
                t1.cancel()
                return res

    @classmethod
    def _hup(cls, session: BotSession) -> None:
        """
        挂起 session
        """
        if session._space_tag is None:
            raise BotSessionError(
                "当前 session 上下文因为缺乏 session_rule 作为唤醒标志，无法挂起"
            )
        elif session._expired:
            raise BotSessionError("过期的 session 不能被挂起")
        session.hup_times.append(time.time())
        cls.STORAGE[session._space_tag].remove(session)
        cls.HUP_STORAGE[session._space_tag].add(session)
        session._awake_signal.clear()

    @classmethod
    def _rouse(cls, session: BotSession) -> None:
        """
        唤醒 session
        """
        cls.HUP_STORAGE[session._space_tag].remove(session)
        cls.STORAGE[session._space_tag].add(session)
        session._awake_signal.set()

    @classmethod
    def _expire(cls, session: BotSession) -> None:
        """
        标记该 session 为过期状态，并进行销毁操作（如果存在于某个 session_space，则从中移除）
        """
        if session._expired:
            return
        session.events.clear()
        session.hup_times.clear()
        session.store_clear()
        session._expired = True
        if session._space_tag:
            cls.STORAGE[session._space_tag].remove(session)

    @classmethod
    def recycle(cls, session: BotSession, alive: bool = False) -> None:
        """
        session 所在方法运行结束后，回收 session。
        默认将 session 销毁。若 alive 为 True，则保留
        """
        session._free_signal.set()
        if not alive:
            cls._expire(session)

    @classmethod
    async def get(cls, event: "BotEvent", handler: "EventHandler") -> Optional[BotSession]:
        """
        handler 内获取 session 方法。自动根据 handler._rule 判断是否需要映射到 session_space 进行存储。
        然后根据具体情况，获取已有 session 或新建 session。当尝试获取非空闲 session 时，如果 handler 指定不等待则返回 None
        """
        if handler._rule:
            # session_space, session._free_signal 竞争，需要加锁
            async with cls.WORK_LOCKS[handler]:
                session = await cls._get_on_rule(event, handler)
                # 必须在锁的保护下修改 session._free_signal
                if session:
                    session._free_signal.clear()
        else:
            session = cls._make(event, handler)
            session._free_signal.clear()

        return session

    @classmethod
    def _make(cls, event: "BotEvent", handler: "EventHandler" = None) -> BotSession:
        """
        内部使用的创建 session 方法。如果 handler 为空，即缺乏 space_tag，则为一次性 session。
        或 handler._rule 为空，则也为一次性 session
        """
        if handler:
            if handler._rule:
                session = BotSession(cls, cls.RESPONDER, handler)
                session.events.append(event)
                cls.STORAGE[handler].add(session)
                return session
        session = BotSession(cls, cls.RESPONDER)
        session.events.append(event)
        return session

    @classmethod
    def make_empty(cls) -> BotSession:
        """
        创建空 session。即不含 event 和 space_tag 标记的 session
        """
        return BotSession(cls, cls.RESPONDER)

    @classmethod
    def make_temp(cls, event: "BotEvent") -> BotSession:
        """
        创建一次性 session。确定无需 session 管理机制时可以使用。
        否则一定使用 cls.get 方法
        """
        return cls._make(event)

    @classmethod
    async def _get_on_rule(
        cls, event: "BotEvent", handler: "EventHandler"
    ) -> Optional[BotSession]:
        """
        根据 handler 具体情况，从对应 session_space 中获取 session 或新建 session。
        或从 hup_session_space 中唤醒 session，或返回 None
        """
        session = None
        check_rule, session_space, hup_session_space, conflict_wait = (
            handler._rule,
            cls.STORAGE[handler],
            cls.HUP_STORAGE[handler],
            handler._wait_flag,
        )

        # for 循环都需要即时 break，保证遍历 session_space 时没有协程切换。因为切换后 session_space 可能发生变动
        for s in session_space:
            if check_rule.compare(s.event, event) and not s._expired:
                session = s
                break
        # 如果会话不存在，生成一个新 session 变量
        if session is None:
            return cls._make(event, handler)
        # 如果会话存在，且未过期，且空闲，则附着到这个 session 上
        if session._free_signal.is_set():
            session.events.append(event)
            return session
        # 如果会话存在，且未过期，但是不空闲，选择不等待
        if not conflict_wait:
            return None
        # 如果会话存在，且未过期，但是不空闲，选择等待，此时就不得不陷入等待（即将发生协程切换）
        await aio.wait(
            [session._free_signal.wait(), session._hup_signal.wait()],
            return_when=aio.FIRST_COMPLETED,
        )
        if session._hup_signal.is_set():
            cls.DEADLOCK_FLAGS[handler].set()
            await session._free_signal.wait()
        """
        重新切换回本协程后，session 有可能变为过期，但此时一定是空闲的。
        同时一定是非挂起状态。因为上面解决了可能存在的挂起死锁问题。
        即使该 session 因过期被所在的 session_space 清除也无妨，因为此处有引用，
        该 session 并不会消失。且此处不操作 session_space，无需担心 session_space 变动
        """
        # 如果过期，生成一个新的 session 变量
        if session._expired:
            return cls._make(event, handler)
        # 如果未过期，则附着到这个 session 上
        else:
            session.events.append(event)
            return session

    @classmethod
    def _activate(cls, action_getter):
        """
        对 action 构造器进行装饰，使产生的 action “活化”。
        让其能自动识别上下文，自动附加触发 event，并自动完成发送过程
        """
        try:
            if SESSION_LOCAL._expired:
                raise BotSessionError(
                    "当前  session 上下文已有过期标记，无法再执行 action 操作"
                )
        except LookupError:
            pass

        @wraps(action_getter)
        async def activated_action(*args, **kwargs):
            action: "BotAction" = await action_getter(*args, **kwargs)
            try:
                if len(SESSION_LOCAL.events) > 0:
                    action._fill_trigger(SESSION_LOCAL.event)
            except LookupError:
                pass

            if not action.ready:
                return action
            try:
                SESSION_LOCAL.actions.append(action)
            except LookupError:
                pass
            if action.resp_id is None:
                return await cls.RESPONDER.take_action(action)
            else:
                return await (await cls.RESPONDER.take_action_wait(action))

        return activated_action


def any_event():
    """
    获取当前 session 上下文下标注为联合类型的 event
    """
    return SESSION_LOCAL.event


def msg_event() -> "MessageEvent":
    """
    获取当前 session 上下文下的 MessageEvent
    """
    return SESSION_LOCAL.event


def notice_event() -> "NoticeEvent":
    """
    获取当前 session 上下文下的 NoticeEvent
    """
    return SESSION_LOCAL.event


def req_evnt() -> "RequestEvent":
    """
    获取当前 session 上下文下的 RequestEvent
    """
    return SESSION_LOCAL.event


def meta_event() -> "MetaEvent":
    """
    获取当前 session 上下文下的 MetaEvent
    """
    return SESSION_LOCAL.event


def msg_text():
    """
    获取当前 session 上下文下的消息的纯文本数据
    """
    return SESSION_LOCAL.event.text


def msg_args():
    """
    获取当前 session 上下文下的解析参数，如果不存在则返回 None
    """
    return SESSION_LOCAL.args


async def pause(overtime: int = None) -> None:
    """
    当前 session 挂起（也就是所在方法的挂起）。直到满足同一 session_rule 的事件重新进入，
    session 所在方法便会被唤醒。但如果设置了超时时间且在唤醒前超时，则会强制唤醒 session，
    并抛出 SessionHupTimeout 异常
    """
    await SESSION_LOCAL.hup(overtime)
