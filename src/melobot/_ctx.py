from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Generator, Generic, Union

from .exceptions import AdapterError, BotRuntimeError, FlowError, LogError, SessionError
from .typ import T
from .utils import singleton

if TYPE_CHECKING:
    from .adapter.base import Adapter
    from .adapter.model import Event
    from .bot.base import Bot
    from .handle.process import Flow, FlowNode
    from .io.base import AbstractInSource, OutSourceT
    from .log.base import GenericLogger
    from .session.base import Session, StoreT
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
        self._lookup_exc_tip = lookup_exc_tip

    def get(self) -> T:
        try:
            return self.__storage__.get()
        except LookupError:
            raise self.lookup_exc_cls(self._lookup_exc_tip) from None

    def try_get(self) -> T | None:
        return self.__storage__.get(None)

    def add(self, ctx: T) -> Token[T]:
        return self.__storage__.set(ctx)

    def remove(self, token: Token[T]) -> None:
        self.__storage__.reset(token)

    @contextmanager
    def on_ctx(self, obj: T) -> Generator[None, None, None]:
        token = self.add(obj)
        try:
            yield
        finally:
            self.remove(token)


_OutSrcFilterType = Callable[["OutSourceT"], bool]


@singleton
class OutSrcFilterCtx(Context[_OutSrcFilterType]):
    def __init__(self) -> None:
        super().__init__("_OUT_SRC_FILTER_CTX", AdapterError)


@dataclass
class EventBuildInfo:
    adapter: "Adapter"
    in_src: "AbstractInSource"


@singleton
class EventBuildInfoCtx(Context[EventBuildInfo]):
    def __init__(self) -> None:
        super().__init__(
            "_EVENT_BUILD_INFO_CTX",
            AdapterError,
            "此时不在活动的事件处理流中，无法获取适配器与输入源的上下文信息",
        )

    def get_adapter_type(self) -> type["Adapter"]:
        from .adapter.base import Adapter

        return Adapter


class _FlowStack(list[str]):
    def append(self, object: str) -> None:
        super().append(object)
        LoggerCtx().get().debug(f"事件处理流记录：{object}")


@dataclass
class FlowInfo:
    flow: "Flow"
    node: "FlowNode"
    next_valid: bool
    stack: _FlowStack = field(default_factory=_FlowStack)


@singleton
class FlowCtx(Context[FlowInfo]):
    def __init__(self) -> None:
        super().__init__(
            "_FLOW_CTX",
            FlowError,
            "此时不在活动的事件处理流中，无法获取处理流信息",
        )


def get_flow_stack() -> tuple[str, ...]:
    return tuple(FlowCtx().get().stack)


@singleton
class BotCtx(Context["Bot"]):
    def __init__(self) -> None:
        super().__init__("_BOT_CTX", BotRuntimeError, "此时未初始化 bot 实例，无法获取")

    def get_type(self) -> type["Bot"]:
        from .bot.base import Bot

        return Bot


def get_bot() -> "Bot":
    return BotCtx().get()


@singleton
class SessionCtx(Context["Session"]):
    def __init__(self) -> None:
        super().__init__(
            "_SESSION_CTX",
            SessionError,
            "此时不在活动的事件处理流中，无法获取会话信息",
        )

    def get_event(self) -> "Event":
        return self.get().event

    def try_get_event(self) -> Union["Event", None]:
        session = self.try_get()
        return session.event if session is not None else None

    def get_event_type(self) -> type["Event"]:
        from .adapter.model import Event

        return Event

    def get_store_type(self) -> type["StoreT"]:
        from .session.base import StoreT

        return StoreT

    def get_rule_type(self) -> type["Rule"]:
        from .session.option import Rule

        return Rule


def get_event() -> "Event":
    return SessionCtx().get_event()


@singleton
class LoggerCtx(Context["GenericLogger"]):
    def __init__(self) -> None:
        super().__init__("_LOGGER_CTX", LogError, "此时未初始化 logger 实例，无法获取")

    def get_type(self) -> type["GenericLogger"]:
        from .log.base import GenericLogger

        return GenericLogger


def get_logger() -> "GenericLogger":
    return LoggerCtx().get()
