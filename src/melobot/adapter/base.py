from __future__ import annotations

import asyncio
from asyncio import create_task
from contextlib import contextmanager
from contextvars import ContextVar, Token

from ..exceptions import BotAdapterError
from ..io.base import (
    AbstractInSource,
    AbstractOutSource,
    EchoPacket_T,
    InPacket_T,
    OutPacket_T,
)
from ..log import get_logger
from ..types import (
    TYPE_CHECKING,
    BetterABC,
    Callable,
    Generator,
    Generic,
    Iterable,
    LiteralString,
    NamedTuple,
    PathLike,
    abstractattr,
    abstractmethod,
)
from ..utils import singleton
from .model import Action_T, ActionHandle, Echo_T, Event_T

if TYPE_CHECKING:
    from ..bot.dispatch import Dispatcher


class AbstractEventFactory(BetterABC, Generic[InPacket_T, Event_T]):
    @abstractmethod
    async def create(self, packet: InPacket_T) -> Event_T:
        raise NotImplementedError


class AbstractOutputFactory(BetterABC, Generic[OutPacket_T, Action_T]):
    @abstractmethod
    async def create(self, action: Action_T) -> OutPacket_T:
        raise NotImplementedError


class AbstractEchoFactory(BetterABC, Generic[EchoPacket_T, Echo_T]):
    @abstractmethod
    async def create(self, packet: EchoPacket_T) -> Echo_T | None:
        raise NotImplementedError


class Adapter(
    BetterABC,
    Generic[InPacket_T, OutPacket_T, EchoPacket_T, Event_T, Action_T, Echo_T],
):
    protocol: LiteralString = abstractattr()
    event_factory: AbstractEventFactory[InPacket_T, Event_T] = abstractattr()
    output_factory: AbstractOutputFactory[OutPacket_T, Action_T] = abstractattr()
    echo_factory: AbstractEchoFactory[EchoPacket_T, Echo_T] = abstractattr()

    def __init__(self) -> None:
        super().__init__()
        self.in_srcs: list[AbstractInSource[InPacket_T]] = []
        self.out_srcs: list[AbstractOutSource[OutPacket_T, EchoPacket_T]] = []
        self.dispatcher: "Dispatcher"

    async def _run(self) -> None:
        async def _input_loop(src: AbstractInSource) -> None:
            logger = get_logger()
            build_local = SrcInfoLocal()
            while True:
                try:
                    packet = await src.input()
                    event = await self.event_factory.create(packet)
                    with build_local.on_ctx(self, src):
                        await self.dispatcher.broadcast(event)
                except Exception:
                    logger.error(f"适配器 {self} 处理输入与分发事件时发生异常")
                    logger.exc(locals=locals())

        if len(ts := tuple(create_task(src.open()) for src in self.in_srcs)):
            await asyncio.wait(ts)
        if len(
            ts := tuple(
                create_task(src.open()) for src in self.out_srcs if not src.opened()
            )
        ):
            await asyncio.wait(ts)
        if len(ts := tuple(create_task(_input_loop(src)) for src in self.in_srcs)):
            await asyncio.wait(ts)

    def call_output(self, action: Action_T) -> tuple[ActionHandle, ...]:
        osrcs: Iterable[AbstractOutSource[OutPacket_T, EchoPacket_T]]
        filter = _OUT_SRC_FILTER.get()
        cur_isrc = SrcInfoLocal().get().in_src

        if filter is not None:
            osrcs = (osrc for osrc in osrcs if filter(osrc))
        elif isinstance(cur_isrc, AbstractOutSource):
            osrcs = (cur_isrc,)
        else:
            osrcs = (self.out_srcs[0],) if len(self.out_srcs) else ()

        return tuple(
            ActionHandle(action, osrc, self.output_factory, self.echo_factory)
            for osrc in osrcs
        )

    @abstractmethod
    def send_text(self, text: str) -> tuple[ActionHandle, ...]:
        raise NotImplementedError

    @abstractmethod
    def send_bytes(self, data: bytes) -> tuple[ActionHandle, ...]:
        raise NotImplementedError

    @abstractmethod
    def send_file(self, path: str | PathLike[str]) -> tuple[ActionHandle, ...]:
        raise NotImplementedError

    @abstractmethod
    def send_video(
        self,
        name: str,
        uri: str | None = None,
        raw: bytes | None = None,
        mimetype: str | None = None,
    ) -> tuple[ActionHandle, ...]:
        raise NotImplementedError

    @abstractmethod
    def send_audio(
        self,
        name: str,
        uri: str | None = None,
        raw: bytes | None = None,
        mimetype: str | None = None,
    ) -> tuple[ActionHandle, ...]:
        raise NotImplementedError


_OUT_SRC_FILTER: ContextVar[Callable[[AbstractOutSource], bool] | None] = ContextVar(
    "_OUT_SRC_FILTER", default=None
)


@contextmanager
def output_filter(
    filter: Callable[[AbstractOutSource], bool]
) -> Generator[None, None, None]:
    token = _OUT_SRC_FILTER.set(filter)
    try:
        yield
    finally:
        _OUT_SRC_FILTER.reset(token)


@singleton
class SrcInfoLocal:
    class BuildInfo(NamedTuple):
        adapter: Adapter
        in_src: AbstractInSource

    def __init__(self) -> None:
        object.__setattr__(self, "__storage__", ContextVar("_EVENT_BUILD_INFO"))
        self.__storage__: ContextVar[SrcInfoLocal.BuildInfo]

    def get(self) -> BuildInfo:
        try:
            return self.__storage__.get()
        except LookupError:
            raise BotAdapterError(
                "此时不在活动的事件处理流中，无法获取适配器与输入源的上下文信息"
            )

    def add(self, ctx: BuildInfo) -> Token:
        return self.__storage__.set(ctx)

    def remove(self, token: Token) -> None:
        self.__storage__.reset(token)

    @contextmanager
    def on_ctx(
        self, adapter: Adapter, in_src: AbstractInSource
    ) -> Generator[None, None, None]:
        token = self.add(SrcInfoLocal.BuildInfo(adapter, in_src))
        try:
            yield
        finally:
            self.remove(token)
