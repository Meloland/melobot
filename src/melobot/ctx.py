from __future__ import annotations

from asyncio import Future
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from enum import Enum

from typing_extensions import (
    TYPE_CHECKING,
    Any,
    Callable,
    Generator,
    Generic,
    Hashable,
    Union,
    cast,
    overload,
)

from .exceptions import AdapterError, BotError, FlowError, SessionError
from .typ.base import T, V
from .typ.cls import SingletonMeta

if TYPE_CHECKING:
    from . import adapter
    from .adapter import model
    from .bot.base import Bot
    from .handle.base import Flow, FlowNode
    from .io import base as io_base
    from .io.base import OutSourceT
    from .log.base import GenericLogger
    from .session.base import Session, SessionStore
    from .session.option import Rule
    from .utils.parse import AbstractParseArgs


class Context(Generic[T], metaclass=SingletonMeta):
    """上下文对象，本质是对 :class:`contextvars.ContextVar` 操作的封装

    继承该基类，可以实现自己的上下文对象。
    任何时候不应该直接实例化该类，而是应该继承实现子类，再使用子类
    """

    def __init__(
        self,
        ctx_name: str,
        lookup_exc_cls: type[BaseException],
        lookup_exc_tip: str | None = None,
    ) -> None:
        """初始化一个上下文对象

        :param ctx_name: 上下文的名称（唯一）
        :param lookup_exc_cls: 当试图获取上下文值失败时，抛出的异常
        :param lookup_exc_tip: 当试图获取上下文值失败时，抛出异常的附加说明
        """
        if self.__class__ is Context:
            raise TypeError(f"任何时候都不应该直接实例化 {Context.__name__}，而应该实现子类")

        self.__storage__ = ContextVar[T](ctx_name)
        self.lookup_exc_cls = lookup_exc_cls
        self.lookup_exc_tip = lookup_exc_tip

    def get(self) -> T:
        """在当前上下文中，获取本上下文对象的上下文值

        :return: 上下文对象的上下文值
        """
        try:
            return self.__storage__.get()
        except LookupError:
            raise self.lookup_exc_cls(self.lookup_exc_tip) from None

    @overload
    def try_get(self, default: V) -> T | V: ...

    @overload
    def try_get(self, default: None = None) -> T | None: ...

    def try_get(self, default: Any = None) -> T | Any:
        """与 :func:`get` 类似，但不存在上下文对象时返回默认值

        :param default: 上下文值不存在时返回的默认值
        :return: 上下文对象的上下文值
        """
        return self.__storage__.get(default)

    def add(self, ctx: T) -> Token[T]:
        """在当前上下文中，添加一个上下文值

        :param ctx: 上下文值
        :return: :class:`contextvars.Token` 对象
        """
        return self.__storage__.set(ctx)

    def remove(self, token: Token[T]) -> None:
        """移除当前上下文中的上下文值

        :param token: 添加时返回的 :class:`contextvars.Token` 对象
        """
        self.__storage__.reset(token)

    @contextmanager
    def unfold(self, obj: T) -> Generator[T, None, None]:
        """展开一个上下文值为 `obj` 的上下文环境，返回上下文管理器

        上下文管理器可 `yield` 上下文值，退出上下文管理器作用域后自动清理

        :param obj: 上下文值
        """
        token = self.add(obj)
        try:
            yield obj
        finally:
            self.remove(token)


_OutSrcFilterType = Callable[["OutSourceT"], bool]


class OutSrcFilterCtx(Context[_OutSrcFilterType]):
    def __init__(self) -> None:
        super().__init__("MELOBOT_OUT_SRC_FILTER", AdapterError)


class FlowRecordStage(Enum):
    """流记录阶段的枚举"""

    FLOW_START = "fs"
    FLOW_EARLY_FINISH = "fef"
    FLOW_FINISH = "ff"

    NODE_START = "ns"
    DEPENDS_NOT_MATCH = "dnm"
    BLOCK = "bl"
    STOP = "st"
    BYPASS = "by"
    REWIND = "re"
    NODE_EARLY_FINISH = "nef"
    NODE_FINISH = "nf"


@dataclass
class FlowRecord:
    """流记录"""

    stage: FlowRecordStage
    flow_name: str
    node_name: str
    event: "model.Event"
    prompt: str = ""


class FlowRecords(list[FlowRecord]):
    def append(self, snapshot: FlowRecord) -> None:
        super().append(snapshot)


class FlowStore(dict[Hashable, Any]):
    """流存储，将会在流运行前初始化，运行结束后销毁"""


@dataclass
class FlowStatus:
    flow: "Flow"
    node: "FlowNode"
    next_valid: bool
    completion: "EventCompletion"
    records: FlowRecords = field(default_factory=FlowRecords)
    store: FlowStore = field(default_factory=FlowStore)


class FlowCtx(Context[FlowStatus]):
    def __init__(self) -> None:
        super().__init__(
            "MELOBOT_FLOW", FlowError, "此时不在活动的事件处理流中，无法获取处理流信息"
        )

    def get_event(self) -> "model.Event":
        session = SessionCtx().try_get()
        if session is not None:
            return session.event
        return self.get().completion.event

    def try_get_event(self) -> Union["model.Event", None]:
        session = SessionCtx().try_get()
        if session is not None:
            return session.event

        status = self.try_get()
        if status is not None:
            return status.completion.event
        return None

    def get_event_type(self) -> type["model.Event"]:
        from .adapter.model import Event

        return Event

    def get_records(self) -> tuple[FlowRecord, ...]:
        return tuple(self.get().records)

    def get_records_type(self) -> type[tuple[FlowRecord, ...]]:
        return tuple[FlowRecord, ...]

    def get_completion(self) -> "EventCompletion":
        return self.get().completion

    def get_store(self) -> FlowStore:
        return self.get().store

    def get_store_type(self) -> type[FlowStore]:
        return FlowStore


class BotCtx(Context["Bot"]):
    def __init__(self) -> None:
        super().__init__("MELOBOT_BOT", BotError, "此时未初始化 bot 实例，无法获取")

    def get_type(self) -> type["Bot"]:
        from .bot.base import Bot

        return Bot

    def get_logger(self) -> "GenericLogger | None":
        return self.get().logger


class SessionCtx(Context["Session"]):
    def __init__(self) -> None:
        super().__init__(
            "MELOBOT_SESSION", SessionError, "此时不在活动的事件处理流中，无法获取会话信息"
        )

    def get_store(self) -> "SessionStore":
        return self.get().store

    def get_rule(self) -> "Rule":
        rule = self.get().rule
        if rule is None:
            raise SessionError("获取会话规则时，预期之外的会话规则为空")
        return rule

    def get_session_type(self) -> type["Session"]:
        from .session.base import Session

        return Session

    def get_store_type(self) -> type["SessionStore"]:
        from .session.base import SessionStore

        return SessionStore

    def get_rule_type(self) -> type["Rule"]:
        from .session.option import Rule

        return Rule


def get_logger_type() -> type["GenericLogger"]:
    from .log.base import GenericLogger

    return GenericLogger


class EventOrigin:
    _FLAG_KEYS = (object(), object())

    def __init__(self, adapter: "adapter.Adapter", in_src: "io_base.AbstractInSource") -> None:
        #: 适配器对象
        self.adapter = adapter
        #: 输入源对象
        self.in_src = in_src

    @classmethod
    def set_origin(cls, event: "model.Event", origin: "EventOrigin") -> None:
        event.flag_set(cls._FLAG_KEYS[0], cls._FLAG_KEYS[1], origin)

    @classmethod
    def get_origin(cls, event: "model.Event") -> EventOrigin:
        origin = event.flag_get(cls._FLAG_KEYS[0], cls._FLAG_KEYS[1])
        return cast(EventOrigin, origin)


# 不使用 dataclass，不用重写任何方法就可哈希
class EventCompletion:
    def __init__(
        self,
        event: "model.Event",
        completed: Future[None],
        owner_flow: "Flow",
        under_session: bool = False,
    ) -> None:
        self.event = event
        self.completed = completed
        self.creator = owner_flow
        self.ctrl_by_session = under_session
        self.flow_ended = False

    def copy(self) -> EventCompletion:
        return EventCompletion(self.event, self.completed, self.creator, self.ctrl_by_session)


class ActionAutoExecCtx(Context[bool]):
    def __init__(self) -> None:
        super().__init__("MELOBOT_ACTION_AUTO_EXEC", AdapterError)


class ParseArgsCtx(Context["AbstractParseArgs"]):
    def __init__(self) -> None:
        super().__init__("MELOBOT_PARSE_ARGS", LookupError, "当前上下文中不存在解析参数")

    def get_args_type(self) -> type["AbstractParseArgs"]:
        from .utils.parse import AbstractParseArgs

        return AbstractParseArgs
