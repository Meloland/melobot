from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Generator, Generic, Union

from .exceptions import AdapterError, BotError, FlowError, LogError, SessionError
from .typ import T
from .utils import singleton

if TYPE_CHECKING:
    from .adapter import model
    from .adapter.base import Adapter
    from .bot.base import Bot
    from .handle.process import Flow, FlowNode
    from .io.base import AbstractInSource, OutSourceT
    from .log.base import GenericLogger
    from .session.base import Session, SessionStore
    from .session.option import Rule


class Context(Generic[T]):
    """上下文对象，本质是对 :class:`contextvars.ContextVar` 操作的封装

    可以继承该基类，实现自己的上下文对象
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

    def try_get(self) -> T | None:
        """与 :func:`get` 类似，但不存在上下文对象时返回 `None`

        :return: 上下文对象的上下文值
        """
        return self.__storage__.get(None)

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
    def in_ctx(self, obj: T) -> Generator[None, None, None]:
        """上下文管理器，展开一个上下文值为 `obj` 的上下文环境

        自动运行 :func:`add` 并在退出上下文环境后运行 :func:`remove`

        :param obj: 上下文值
        """
        token = self.add(obj)
        try:
            yield
        finally:
            self.remove(token)


_OutSrcFilterType = Callable[["OutSourceT"], bool]


@singleton
class OutSrcFilterCtx(Context[_OutSrcFilterType]):
    def __init__(self) -> None:
        super().__init__("MELOBOT_OUT_SRC_FILTER", AdapterError)


@dataclass
class EventBuildInfo:
    adapter: "Adapter"
    in_src: "AbstractInSource"


@singleton
class EventBuildInfoCtx(Context[EventBuildInfo]):
    def __init__(self) -> None:
        super().__init__(
            "MELOBOT_EVENT_BUILD_INFO",
            AdapterError,
            "此时不在活动的事件处理流中，无法获取适配器与输入源的上下文信息",
        )

    def get_adapter_type(self) -> type["Adapter"]:
        from .adapter.base import Adapter

        return Adapter


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


class FlowStore(dict[str, Any]):
    """流存储，将会在流运行前初始化，运行结束后销毁"""


@dataclass
class FlowStatus:
    event: "model.Event"
    flow: "Flow"
    node: "FlowNode"
    next_valid: bool
    records: FlowRecords = field(default_factory=FlowRecords)
    store: FlowStore = field(default_factory=FlowStore)


@singleton
class FlowCtx(Context[FlowStatus]):
    def __init__(self) -> None:
        super().__init__(
            "MELOBOT_FLOW",
            FlowError,
            "此时不在活动的事件处理流中，无法获取处理流信息",
        )

    def get_event(self) -> "model.Event":
        return self.get().event

    def try_get_event(self) -> Union["model.Event", None]:
        status = self.try_get()
        return status.event if status is not None else None

    def get_event_type(self) -> type["model.Event"]:
        from .adapter.model import Event

        return Event

    def get_store(self) -> FlowStore:
        return self.get().store

    def get_store_type(self) -> type[FlowStore]:
        return FlowStore


@singleton
class BotCtx(Context["Bot"]):
    def __init__(self) -> None:
        super().__init__("MELOBOT_BOT", BotError, "此时未初始化 bot 实例，无法获取")

    def get_type(self) -> type["Bot"]:
        from .bot.base import Bot

        return Bot


@singleton
class SessionCtx(Context["Session"]):
    def __init__(self) -> None:
        super().__init__(
            "MELOBOT_SESSION",
            SessionError,
            "此时不在活动的事件处理流中，无法获取会话信息",
        )

    def get_store(self) -> "SessionStore":
        return self.get().store

    def get_store_type(self) -> type["SessionStore"]:
        from .session.base import SessionStore

        return SessionStore

    def get_rule_type(self) -> type["Rule"]:
        from .session.option import Rule

        return Rule


@singleton
class LoggerCtx(Context["GenericLogger"]):
    def __init__(self) -> None:
        super().__init__("MELOBOT_LOGGER", LogError, "此时未初始化 logger 实例，无法获取")

    def get_type(self) -> type["GenericLogger"]:
        from .log.base import GenericLogger

        return GenericLogger


@singleton
class ActionManualSignalCtx(Context[bool]):
    def __init__(self) -> None:
        super().__init__("MELOBOT_ACTION_AUTO_SIGNAL", AdapterError)
