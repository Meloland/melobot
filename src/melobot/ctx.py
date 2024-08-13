from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass

from .exceptions import (
    BotAdapterError,
    BotLogError,
    BotRuntimeError,
    BotSessionError,
    ProcessFlowError,
)
from .typ import TYPE_CHECKING, Callable, Generator, Generic, T, Union
from .utils import singleton

if TYPE_CHECKING:
    from .adapter.base import Adapter
    from .adapter.model import Event
    from .bot.base import Bot
    from .handle.process import ProcessFlow, ProcessNode
    from .io.base import AbstractInSource, OutSource_T
    from .log import Logger
    from .session.base import Session


class Context(Generic[T]):
    def __init__(
        self,
        ctx_name: str,
        lookup_exc_cls: type[BaseException],
        lookup_exc_tip: str | None = None,
    ) -> None:
        self.__storage__ = ContextVar[T](ctx_name)
        self._lookup_exc_cls = lookup_exc_cls
        self._lookup_exc_tip = lookup_exc_tip

    def get(self) -> T:
        try:
            return self.__storage__.get()
        except LookupError:
            raise self._lookup_exc_cls(self._lookup_exc_tip)

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


_OutSrcFilterType = Callable[["OutSource_T"], bool]


@singleton
class OutSrcFilterCtx(Context[_OutSrcFilterType]):
    def __init__(self) -> None:
        super().__init__("_OUT_SRC_FILTER_CTX", BotAdapterError)


@dataclass
class EventBuildInfo:
    adapter: "Adapter"
    in_src: "AbstractInSource"


@singleton
class EventBuildInfoCtx(Context[EventBuildInfo]):
    def __init__(self) -> None:
        super().__init__(
            "_EVENT_BUILD_INFO_CTX",
            BotAdapterError,
            "此时不在活动的事件处理流中，无法获取适配器与输入源的上下文信息",
        )


@dataclass
class FlowInfo:
    flow: "ProcessFlow"
    node: "ProcessNode"
    next_valid: bool
    stack: list[str]


@singleton
class FlowCtx(Context[FlowInfo]):
    def __init__(self) -> None:
        super().__init__(
            "_FLOW_CTX",
            ProcessFlowError,
            "此时不在活动的事件处理流中，无法获取处理流信息",
        )


@singleton
class BotCtx(Context["Bot"]):
    def __init__(self) -> None:
        super().__init__("_BOT_CTX", BotRuntimeError, "此时未初始化 bot 实例，无法获取")


@singleton
class SessionCtx(Context["Session"]):
    def __init__(self) -> None:
        super().__init__(
            "_SESSION_CTX",
            BotSessionError,
            "此时不在活动的事件处理流中，无法获取会话信息",
        )

    def try_get_event(self) -> Union["Event", None]:
        session = self.try_get()
        return session.event if session is not None else None


@singleton
class LoggerCtx(Context["Logger"]):
    def __init__(self) -> None:
        super().__init__("_LOGGER_CTX", BotLogError, "此时未初始化 logger 实例，无法获取")
