from __future__ import annotations

import asyncio
from asyncio import create_task
from contextlib import AsyncExitStack, _GeneratorContextManager, asynccontextmanager
from enum import Enum
from os import PathLike
from typing import (
    TYPE_CHECKING,
    AsyncGenerator,
    Callable,
    Generic,
    Iterable,
    NoReturn,
    Sequence,
    TypeVar,
    cast,
    final,
)

from typing_extensions import LiteralString, Self

from .._ctx import EventBuildInfo, EventBuildInfoCtx, LoggerCtx, OutSrcFilterCtx
from .._hook import HookBus
from ..exceptions import AdapterError
from ..io.base import (
    AbstractOutSource,
    EchoPacketT,
    InPacketT,
    InSourceT,
    OutPacketT,
    OutSourceT,
)
from ..log.base import LogLevel
from ..typ import BetterABC, abstractattr, abstractmethod
from .content import Content
from .model import ActionHandle, ActionT, EchoT, Event, EventT

if TYPE_CHECKING:
    from ..bot.dispatch import Dispatcher


_EVENT_BUILD_INFO_CTX = EventBuildInfoCtx()
_OUT_SRC_FILTER_CTX = OutSrcFilterCtx()


class AbstractEventFactory(BetterABC, Generic[InPacketT, EventT]):
    @abstractmethod
    async def create(self, packet: InPacketT) -> EventT:
        raise NotImplementedError


EventFactoryT = TypeVar("EventFactoryT", bound=AbstractEventFactory)


class AbstractOutputFactory(BetterABC, Generic[OutPacketT, ActionT]):
    @abstractmethod
    async def create(self, action: ActionT) -> OutPacketT:
        raise NotImplementedError


OutputFactoryT = TypeVar("OutputFactoryT", bound=AbstractOutputFactory)


class AbstractEchoFactory(BetterABC, Generic[EchoPacketT, EchoT]):
    @abstractmethod
    async def create(self, packet: EchoPacketT) -> EchoT | None:
        raise NotImplementedError


EchoFactoryT = TypeVar("EchoFactoryT", bound=AbstractEchoFactory)


class AdapterLifeSpan(Enum):
    BEFORE_EVENT = "be"
    BEFORE_ACTION = "ba"


class Adapter(
    BetterABC,
    Generic[EventFactoryT, OutputFactoryT, EchoFactoryT, InSourceT, OutSourceT],
):
    # pylint: disable=duplicate-code
    # pylint: disable=unused-argument

    protocol: LiteralString = abstractattr()
    event_factory: EventFactoryT = abstractattr()
    output_factory: OutputFactoryT = abstractattr()
    echo_factory: EchoFactoryT = abstractattr()

    def __init__(self) -> None:
        super().__init__()
        self.in_srcs: list[InSourceT] = []
        self.out_srcs: list[OutSourceT] = []
        self.dispatcher: "Dispatcher"

        self._inited = False
        self._life_bus = HookBus[AdapterLifeSpan](AdapterLifeSpan)

    async def __adapter_input_loop__(self, src: InSourceT) -> NoReturn:
        logger = LoggerCtx().get()
        while True:
            try:
                packet = await src.input()
                event = await self.event_factory.create(  # pylint: disable=no-member
                    packet
                )
                with _EVENT_BUILD_INFO_CTX.on_ctx(EventBuildInfo(self, src)):
                    await self._life_bus.emit(
                        AdapterLifeSpan.BEFORE_EVENT, wait=True, args=(event,)
                    )
                    asyncio.create_task(self.dispatcher.broadcast(event))
            except Exception:
                logger.exception(f"适配器 {self} 处理输入与分发事件时发生异常")
                logger.generic_obj("异常点局部变量：", locals(), level=LogLevel.ERROR)

    @asynccontextmanager
    @final
    async def __adapter_launch__(self) -> AsyncGenerator[Self, None]:
        if self._inited:
            raise AdapterError(f"适配器 {self} 已在运行，不能重复启动")

        async with AsyncExitStack() as stack:
            out_src_ts = tuple(
                create_task(stack.enter_async_context(src)) for src in self.out_srcs
            )
            if len(out_src_ts):
                await asyncio.wait(out_src_ts)

            in_src_ts = tuple(
                create_task(stack.enter_async_context(src))
                for src in self.in_srcs
                if not src.opened()
            )
            if len(in_src_ts):
                await asyncio.wait(in_src_ts)

            for src in self.in_srcs:
                create_task(self.__adapter_input_loop__(src))

            self._inited = True
            yield self

    @final
    def filter_out(
        self, filter: Callable[[OutSourceT], bool]
    ) -> _GeneratorContextManager[None]:
        return _OUT_SRC_FILTER_CTX.on_ctx(filter)

    @final
    async def call_output(self, action: ActionT) -> tuple[ActionHandle, ...]:
        osrcs: Iterable[OutSourceT]
        filter = _OUT_SRC_FILTER_CTX.try_get()
        cur_isrc = _EVENT_BUILD_INFO_CTX.get().in_src

        if filter is not None:
            osrcs = (osrc for osrc in self.out_srcs if filter(osrc))
        elif isinstance(cur_isrc, AbstractOutSource):
            osrcs = (cast(OutSourceT, cur_isrc),)
        else:
            osrcs = (self.out_srcs[0],) if len(self.out_srcs) else ()

        await self._life_bus.emit(
            AdapterLifeSpan.BEFORE_ACTION, wait=True, args=(action,)
        )
        return tuple(
            ActionHandle(action, osrc, self.output_factory, self.echo_factory)
            for osrc in osrcs
        )

    @abstractmethod
    async def send_text(self, text: str) -> tuple[ActionHandle, ...]:
        raise NotImplementedError

    async def send_media(
        self,
        name: str,
        raw: bytes | None = None,
        url: str | None = None,
        mimetype: str | None = None,
    ) -> tuple[ActionHandle, ...]:
        return await self.send_text(f"[melobot media: {name}]")

    async def send_image(
        self,
        name: str,
        raw: bytes | None = None,
        url: str | None = None,
        mimetype: str | None = None,
    ) -> tuple[ActionHandle, ...]:
        return await self.send_text(f"[melobot image: {name}]")

    async def send_audio(
        self,
        name: str,
        raw: bytes | None = None,
        url: str | None = None,
        mimetype: str | None = None,
    ) -> tuple[ActionHandle, ...]:
        return await self.send_text(f"[melobot audio: {name}]")

    async def send_voice(
        self,
        name: str,
        raw: bytes | None = None,
        url: str | None = None,
        mimetype: str | None = None,
    ) -> tuple[ActionHandle, ...]:
        return await self.send_text(f"[melobot voice: {name}]")

    async def send_video(
        self,
        name: str,
        raw: bytes | None = None,
        url: str | None = None,
        mimetype: str | None = None,
    ) -> tuple[ActionHandle, ...]:
        return await self.send_text(f"[melobot video: {name}]")

    async def send_file(
        self, name: str, path: str | PathLike[str]
    ) -> tuple[ActionHandle, ...]:
        return await self.send_text(f"[melobot file: {name}]")

    async def send_refer(
        self, event: Event, contents: Sequence[Content] | None = None
    ) -> tuple[ActionHandle, ...]:
        return await self.send_text(
            f"[melobot refer: {event.__class__.__name__}({event.id})]"
        )
