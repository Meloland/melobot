from __future__ import annotations

import asyncio
from asyncio import create_task
from contextlib import _GeneratorContextManager

from .._ctx import EventBuildInfo, EventBuildInfoCtx, OutSrcFilterCtx
from ..io.base import (
    AbstractOutSource,
    EchoPacket_T,
    InPacket_T,
    InSource_T,
    OutPacket_T,
    OutSource_T,
)
from ..log import get_logger
from ..typ import (
    TYPE_CHECKING,
    BetterABC,
    Callable,
    Generic,
    Iterable,
    LiteralString,
    PathLike,
    TypeVar,
    abstractattr,
    abstractmethod,
    cast,
)
from .model import Action_T, ActionHandle, Echo_T, Event_T

if TYPE_CHECKING:
    from ..bot.dispatch import Dispatcher


_EVENT_BUILD_INFO_CTX = EventBuildInfoCtx()
_OUT_SRC_FILTER_CTX = OutSrcFilterCtx()


class AbstractEventFactory(BetterABC, Generic[InPacket_T, Event_T]):
    @abstractmethod
    async def create(self, packet: InPacket_T) -> Event_T:
        raise NotImplementedError


EventFactory_T = TypeVar("EventFactory_T", bound=AbstractEventFactory)


class AbstractOutputFactory(BetterABC, Generic[OutPacket_T, Action_T]):
    @abstractmethod
    async def create(self, action: Action_T) -> OutPacket_T:
        raise NotImplementedError


OutputFactory_T = TypeVar("OutputFactory_T", bound=AbstractOutputFactory)


class AbstractEchoFactory(BetterABC, Generic[EchoPacket_T, Echo_T]):
    @abstractmethod
    async def create(self, packet: EchoPacket_T) -> Echo_T | None:
        raise NotImplementedError


EchoFactory_T = TypeVar("EchoFactory_T", bound=AbstractEchoFactory)


class Adapter(
    BetterABC,
    Generic[EventFactory_T, OutputFactory_T, EchoFactory_T, InSource_T, OutSource_T],
):
    protocol: LiteralString = abstractattr()
    event_factory: EventFactory_T = abstractattr()
    output_factory: OutputFactory_T = abstractattr()
    echo_factory: EchoFactory_T = abstractattr()

    def __init__(self) -> None:
        super().__init__()
        self.in_srcs: list[InSource_T] = []
        self.out_srcs: list[OutSource_T] = []
        self.dispatcher: "Dispatcher"

    async def _run(self) -> None:
        async def _input_loop(src: InSource_T) -> None:
            logger = get_logger()
            while True:
                try:
                    packet = await src.input()
                    event = await self.event_factory.create(packet)
                    with _EVENT_BUILD_INFO_CTX.on_ctx(EventBuildInfo(self, src)):
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

    def out_filter(
        self, filter: Callable[[OutSource_T], bool]
    ) -> _GeneratorContextManager[None]:
        return _OUT_SRC_FILTER_CTX.on_ctx(filter)

    def call_output(self, action: Action_T) -> tuple[ActionHandle, ...]:
        osrcs: Iterable[OutSource_T]
        filter = _OUT_SRC_FILTER_CTX.try_get()
        cur_isrc = _EVENT_BUILD_INFO_CTX.get().in_src

        if filter is not None:
            osrcs = (osrc for osrc in self.out_srcs if filter(osrc))
        elif isinstance(cur_isrc, AbstractOutSource):
            osrcs = (cast(OutSource_T, cur_isrc),)
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
