import asyncio
from functools import wraps

from ..base.abc import BotEvent, Event_T
from ..base.exceptions import BotSessionError, BotSessionTimeout
from ..base.ioc import PendingDepend
from ..base.typing import (
    TYPE_CHECKING,
    Any,
    AsyncCallable,
    Callable,
    Optional,
    P,
    Union,
    cast,
)
from .session import SESSION_LOCAL, ActionHandle, ActionResponse, BotSession, SessionRule

if TYPE_CHECKING:
    from ..base.abc import BotAction, ParseArgs
    from ..bot.init import BotLocal, MeloBot
    from ..models.event import MessageEvent, MetaEvent, NoticeEvent, RequestEvent
    from ..plugin.handler import EventHandler


class BotSessionManager:
    STORAGE: dict["EventHandler", set[BotSession]] = {}
    HUP_STORAGE: dict["EventHandler", set[BotSession]] = {}
    # 各个 handler 对饮的操作锁
    WORK_LOCKS: dict["EventHandler", asyncio.Lock] = {}
    # 用来标记 cls.get 等待一个挂起的会话时的死锁
    DEADLOCK_FLAGS: dict["EventHandler", asyncio.Event] = {}
    # 对应每个 handler 的 try_attach 过程的操作锁
    ATTACH_LOCKS: dict["EventHandler", asyncio.Lock] = {}
    BOT_CTX: "MeloBot"

    @classmethod
    def _bind(cls, bot_local_var: "BotLocal") -> None:
        cls.BOT_CTX = bot_local_var  # type: ignore[assignment]

    @classmethod
    def register(cls, handler: "EventHandler") -> None:
        """以 handler 为键，注册 handler 对应的会话空间、操作锁和挂起会话空间"""
        cls.STORAGE[handler] = set()
        cls.WORK_LOCKS[handler] = asyncio.Lock()
        cls.HUP_STORAGE[handler] = set()
        cls.DEADLOCK_FLAGS[handler] = asyncio.Event()
        cls.ATTACH_LOCKS[handler] = asyncio.Lock()

    @classmethod
    def fill_args(cls, session: BotSession, args: Union["ParseArgs", None]) -> None:
        session.args = args

    @classmethod
    def _attach(cls, event: Event_T, handler: "EventHandler") -> bool:
        """会话 附着操作，临界区操作。只能在 cls.try_attach 中进行"""
        session = None

        for s in cls.HUP_STORAGE[handler]:
            # 会话的挂起方法，保证会话一定未过期，因此不进行过期检查
            handler._rule = cast(SessionRule, handler._rule)
            if handler._rule.compare(s.event, event):
                session = s
                break

        # 如果获得一个挂起的 会话，它一定是可附着的，附着后需要唤醒
        if session:
            session.event = event
            cls._rouse(session)
            return True
        return False

    @classmethod
    async def try_attach(cls, event: Event_T, handler: "EventHandler") -> bool:
        """检查是否有挂起的会话可供 event 附着。 如果有则附着并唤醒，并返回 True。否则返回 False。"""
        if handler._rule is None:
            return False

        async with cls.ATTACH_LOCKS[handler]:
            t1 = asyncio.create_task(cls.DEADLOCK_FLAGS[handler].wait(), name="flag")
            t2 = asyncio.create_task(cls.WORK_LOCKS[handler].acquire(), name="lock")
            done, _ = await asyncio.wait([t1, t2], return_when=asyncio.FIRST_COMPLETED)

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
    async def _hup(cls, session: BotSession, overtime: Optional[float] = None) -> None:
        """挂起 会话"""
        if session._space_tag is None:
            raise BotSessionError("当前会话上下文因为缺乏会话规则作为唤醒标志，无法挂起")
        elif session._expired:
            raise BotSessionError("过期的会话不能被挂起")

        cls.fill_args(session, None)
        cls.STORAGE[session._space_tag].remove(session)
        cls.HUP_STORAGE[session._space_tag].add(session)
        session._awake_signal.clear()

        if overtime is None:
            await session._awake_signal.wait()
        elif overtime <= 0:
            raise BotSessionError("会话 挂起超时时间（秒数）必须 > 0")

        else:
            _awake = asyncio.create_task(session._awake_signal.wait())
            _timeout = asyncio.create_task(asyncio.sleep(overtime))
            await asyncio.wait([_awake, _timeout], return_when=asyncio.FIRST_COMPLETED)

            if not session._awake_signal.is_set():
                cls._rouse(session)
                raise BotSessionTimeout("会话 挂起超时")

    @classmethod
    def _rouse(cls, session: BotSession) -> None:
        """唤醒 会话"""
        if session._space_tag is None:
            raise BotSessionError("当前会话上下文缺乏会话规则，无法唤醒")

        cls.HUP_STORAGE[session._space_tag].remove(session)
        cls.STORAGE[session._space_tag].add(session)
        session._awake_signal.set()

    @classmethod
    def _expire(cls, session: BotSession) -> None:
        """标记该会话为过期状态，并进行销毁操作（如果存在于某个 session_space，则从中移除）"""
        if session._expired:
            return

        session.store.clear()
        session._expired = True
        if session._space_tag:
            cls.STORAGE[session._space_tag].remove(session)

    @classmethod
    def recycle(cls, session: BotSession, alive: bool = False) -> None:
        """会话 所在方法运行结束后，回收 会话。 默认将会话销毁。若 alive 为 True，则保留"""
        session._free_signal.set()
        if not alive:
            cls._expire(session)

    @classmethod
    async def get(cls, event: Event_T, handler: "EventHandler") -> Optional[BotSession]:
        """Handler 内获取会话方法。自动根据 handler._rule 判断是否需要映射到 session_space 进行存储。
        然后根据具体情况，获取已有会话或新建 会话。当尝试获取非空闲会话时，如果 handler 指定不等待则返回
        None."""
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
    def _make(
        cls, event: Event_T, handler: Optional["EventHandler"] = None
    ) -> BotSession:
        """内部使用的创建会话方法。如果 handler 为空，即缺乏 space_tag，则为一次性 会话。 或 handler._rule
        为空，则也为一次性 会话."""
        if handler and handler._rule:
            session = BotSession(event, cls, handler)
            cls.STORAGE[handler].add(session)
            return session

        session = BotSession(event, cls)
        return session

    @classmethod
    def make_temp(cls, event: Event_T) -> BotSession:
        """创建临时 会话。确定无需会话管理机制时可以使用。 否则一定使用 cls.get 方法"""
        return cls._make(event)

    @classmethod
    async def _get_on_rule(
        cls, event: Event_T, handler: "EventHandler"
    ) -> Optional[BotSession]:
        """根据 handler 具体情况，从对应 session_space 中获取会话或新建 会话，或返回 None"""
        session = None
        check_rule, session_space, conflict_wait = (
            handler._rule,
            cls.STORAGE[handler],
            handler._wait_flag,
        )

        # for 循环都需要即时 break，保证遍历 session_space 时没有协程切换。因为切换后 session_space 可能发生变动
        for s in session_space:
            check_rule = cast(SessionRule, check_rule)
            if check_rule.compare(s.event, event) and not s._expired:
                session = s
                break

        # 如果会话不存在，生成一个新会话变量
        if session is None:
            return cls._make(event, handler)

        # 如果会话存在，且未过期，且空闲，则附着到这个会话上
        if session._free_signal.is_set():
            session.event = event
            return session

        # 如果会话存在，且未过期，但是不空闲，选择不等待
        if not conflict_wait:
            return None

        # 如果会话存在，且未过期，但是不空闲，选择等待，此时就不得不陷入等待（即将发生协程切换）
        _free = asyncio.create_task(session._free_signal.wait())
        _hup = asyncio.create_task(session._hup_signal.wait())
        await asyncio.wait([_free, _hup], return_when=asyncio.FIRST_COMPLETED)

        if session._hup_signal.is_set():
            cls.DEADLOCK_FLAGS[handler].set()
            await session._free_signal.wait()

        """
        重新切换回本协程后，会话 有可能变为过期，但此时一定是空闲的。
        同时一定是非挂起状态。因为上面解决了可能存在的挂起死锁问题。
        即使该会话因过期被所在的 session_space 清除也无妨，因为此处有引用，
        该会话并不会消失。且此处不操作 session_space，无需担心 session_space 变动
        """
        # 如果过期，生成一个新的会话变量
        if session._expired:
            return cls._make(event, handler)
        # 如果未过期，则附着到这个会话上
        else:
            session.event = event
            return session

    @classmethod
    def _handle(
        cls, action_getter: Callable[P, "BotAction"]
    ) -> Callable[P, "ActionHandle"]:

        @wraps(action_getter)
        def wrapped_func(*args: Any, **kwargs: Any) -> ActionHandle:
            try:
                if SESSION_LOCAL._expired:
                    raise BotSessionError(
                        "当前会话上下文已有过期标记，无法再执行 action 操作"
                    )
            except LookupError:
                pass

            action: "BotAction" = action_getter(*args, **kwargs)

            if cls.BOT_CTX.logger._check_level("DEBUG"):
                cls.BOT_CTX.logger.debug(
                    f"action {action:hexid} 构建完成（当前会话上下文：{SESSION_LOCAL:hexid}）"
                )

            try:
                action._fill_trigger(SESSION_LOCAL.event)
            except LookupError:
                pass

            exec_meth: AsyncCallable[["BotAction"], asyncio.Future[ActionResponse] | None]
            if action.resp_id is None:
                exec_meth = cls.BOT_CTX._responder.take_action
            else:
                exec_meth = cls.BOT_CTX._responder.take_action_wait

            handle = ActionHandle(action, exec_meth, action.resp_id is not None)
            if not action._ready:
                return handle
            else:
                handle.execute()
                return handle

        return wrapped_func


def any_event() -> BotEvent:
    """获取当前会话下的事件

    :return: 具体的事件
    """
    try:
        return SESSION_LOCAL.event
    except LookupError:
        return PendingDepend(lambda: SESSION_LOCAL.event)  # type: ignore[return-value]


def msg_event() -> "MessageEvent":
    """获取当前会话下的事件

    确定此事件是消息事件时使用，例如在消息事件的处理函数中，使用该方法即可获得精准的类型提示

    :return: 具体的事件
    """
    return cast("MessageEvent", any_event())


def notice_event() -> "NoticeEvent":
    """获取当前会话下的事件

    确定此事件是通知事件时使用，例如在通知事件的处理函数中，使用该方法即可获得精准的类型提示

    :return: 具体的事件
    """
    return cast("NoticeEvent", any_event())


def req_event() -> "RequestEvent":
    """获取当前会话下的事件

    确定此事件是请求事件时使用，例如在请求事件的处理函数中，使用该方法即可获得精准的类型提示

    :return: 具体的事件
    """
    return cast("RequestEvent", any_event())


def meta_event() -> "MetaEvent":
    """获取当前会话下的事件

    确定此事件是元事件时使用，例如在元事件的处理函数中，使用该方法即可获得精准的类型提示

    :return: 具体的事件
    """
    return cast("MetaEvent", any_event())


def msg_text() -> str:
    """获取当前会话下的，消息事件的纯文本内容的合并字符串。
    等价于手动读取消息事件的 :attr:`~.MessageEvent.text` 属性

    只能在确定当前会话下必为消息事件时使用

    :return: 纯文本内容的合并字符串
    """
    try:
        return SESSION_LOCAL.event.text
    except LookupError:
        return PendingDepend(lambda: SESSION_LOCAL.event.text)  # type: ignore[return-value]


def msg_args() -> list[Any] | None:
    """获取当前会话下的消息事件的所有解析参数值。

    只能在确定当前会话下必为消息事件时使用

    :return: 解析参数值列表或 :obj:`None`
    """

    def _getter() -> list[Any] | None:
        if SESSION_LOCAL.args is not None:
            return SESSION_LOCAL.args.vals
        else:
            return None

    try:
        return _getter()
    except LookupError:
        return PendingDepend(_getter)  # type: ignore[return-value]


def session_store() -> dict:
    """返回当前会话的存储字典对象，可直接操作

    会话存储字典对象用于在会话层面保存和共享数据。

    :return: 会话的存储字典对象
    """
    try:
        return SESSION_LOCAL.store
    except LookupError:
        return PendingDepend(lambda: SESSION_LOCAL.store)  # type: ignore[return-value]


async def pause(overtime: Optional[float] = None) -> None:
    """会话暂停直到被同一会话的事件唤醒

    暂时停止本会话。当本会话的会话规则判断有属于本会话的另一事件发生，
    本会话将自动被唤醒。

    可指定超时时间。如果超时时间结束会话仍未被唤醒，此时将会被强制唤醒，
    并抛出一个 :class:`.BotSessionTimeout` 异常。可以捕获此异常，
    实现自定义的超时处理逻辑

    :param overtime: 超时时间
    """
    try:
        await BotSessionManager._hup(SESSION_LOCAL._get_var(), overtime)
    except LookupError:
        raise BotSessionError("当前会话上下文不存在，因此无法使用本方法")


def dispose() -> None:
    """销毁当前会话

    将会清理会话的存储空间，并将会话标记为过期态。
    此时调用该方法的函数依然可以运行，但是此会话状态下无法再进行行为操作。

    一般来说，会话将会自动销毁。
    只有在绑定事件处理函数时使用 `session_hold=True`，才会需要使用此函数。

    """
    try:
        BotSessionManager._expire(SESSION_LOCAL._get_var())
    except LookupError:
        raise BotSessionError("当前会话上下文不存在，因此无法使用本方法")
