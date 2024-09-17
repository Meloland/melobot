from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Generator, Generic, Union

from .exceptions import AdapterError, BotError, FlowError, LogError, SessionError
from .typ import T
from .utils import singleton

if TYPE_CHECKING:
    from .adapter.base import Adapter
    from .adapter.model import Event
    from .bot.base import Bot
    from .handle.process import Flow, FlowNode
    from .io.base import AbstractInSource, OutSourceT
    from .log.base import GenericLogger
    from .session.base import Session, SessionStore
    from .session.option import Rule


class Context(Generic[T]):
    def __init__(
        self,
        ctx_name: str,
        lookup_exc_cls: type[BaseException],
        lookup_exc_tip: str | None = None,
    ) -> None:
        self.__storage__ = ContextVar[T](ctx_name)
        self.lookup_exc_cls = lookup_exc_cls
        self.lookup_exc_tip = lookup_exc_tip

    def get(self) -> T:
        try:
            return self.__storage__.get()
        except LookupError:
            raise self.lookup_exc_cls(self.lookup_exc_tip) from None

    def try_get(self) -> T | None:
        return self.__storage__.get(None)

    def add(self, ctx: T) -> Token[T]:
        return self.__storage__.set(ctx)

    def remove(self, token: Token[T]) -> None:
        self.__storage__.reset(token)

    @contextmanager
    def in_ctx(self, obj: T) -> Generator[None, None, None]:
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
    stage: FlowRecordStage
    flow_name: str
    node_name: str
    event: "Event"
    msg: str = ""


class FlowRecords(list[FlowRecord]):
    def append(self, snapshot: FlowRecord) -> None:
        super().append(snapshot)


class FlowStore(dict[str, Any]): ...


@dataclass
class FlowStatus:
    event: "Event"
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

    def get_event(self) -> "Event":
        return self.get().event

    def try_get_event(self) -> Union["Event", None]:
        status = self.try_get()
        return status.event if status is not None else None

    def get_event_type(self) -> type["Event"]:
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
