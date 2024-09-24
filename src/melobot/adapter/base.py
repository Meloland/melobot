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
    cast,
    final,
)

from typing_extensions import LiteralString, Self, TypeVar

from .._hook import HookBus
from ..ctx import EventBuildInfo, EventBuildInfoCtx, LoggerCtx, OutSrcFilterCtx
from ..exceptions import AdapterError
from ..io.base import (
    AbstractInSource,
    AbstractOutSource,
    EchoPacketT,
    InPacketT,
    InSourceT,
    OutPacketT,
    OutSourceT,
)
from ..log.base import LogLevel
from ..typ import AsyncCallable, BetterABC, P, abstractmethod
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
    STARTED = "sta"
    STOPPED = "sto"


class Adapter(
    BetterABC,
    Generic[
        EventFactoryT,
        OutputFactoryT,
        EchoFactoryT,
        ActionT,
        InSourceT,
        OutSourceT,
    ],
):
    # pylint: disable=duplicate-code
    # pylint: disable=unused-argument

    def __init__(
        self,
        protocol: LiteralString,
        event_factory: EventFactoryT,
        output_factory: OutputFactoryT,
        echo_factory: EchoFactoryT,
    ) -> None:
        super().__init__()
        self.protocol = protocol

        self.in_srcs: list[InSourceT] = []
        self.out_srcs: list[OutSourceT] = []
        self.dispatcher: "Dispatcher"
        self._event_factory = event_factory
        self._output_factory = output_factory
        self._echo_factory = echo_factory

        self._inited = False
        self._life_bus = HookBus[AdapterLifeSpan](AdapterLifeSpan)

    @final
    def on(
        self, *period: AdapterLifeSpan
    ) -> Callable[[AsyncCallable[P, None]], AsyncCallable[P, None]]:
        def wrapped(func: AsyncCallable[P, None]) -> AsyncCallable[P, None]:
            for type in period:
                self._life_bus.register(type, func)
            return func

        return wrapped

    @final
    def get_isrcs(self, filter: Callable[[InSourceT], bool]) -> set[InSourceT]:
        return set(src for src in self.in_srcs if filter(src))

    @final
    def get_osrcs(self, filter: Callable[[OutSourceT], bool]) -> set[OutSourceT]:
        return set(src for src in self.out_srcs if filter(src))

    @final
    async def __adapter_input_loop__(self, src: InSourceT) -> NoReturn:
        logger = LoggerCtx().get()
        while True:
            try:
                packet = await src.input()
                event = await self._event_factory.create(packet)
                with _EVENT_BUILD_INFO_CTX.in_ctx(EventBuildInfo(self, src)):
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

        try:
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
                await self._life_bus.emit(AdapterLifeSpan.STARTED)
                yield self

        finally:
            if self._inited:
                await self._life_bus.emit(AdapterLifeSpan.STOPPED, wait=True)

    @final
    def filter_out(
        self, filter: Callable[[OutSourceT], bool]
    ) -> _GeneratorContextManager[None]:
        return _OUT_SRC_FILTER_CTX.in_ctx(filter)

    async def call_output(self, action: ActionT) -> tuple[ActionHandle, ...]:
        osrcs: Iterable[OutSourceT]
        filter = _OUT_SRC_FILTER_CTX.try_get()
        cur_isrc: AbstractInSource | None
        if info := _EVENT_BUILD_INFO_CTX.try_get():
            cur_isrc = info.in_src
        else:
            cur_isrc = None

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
            ActionHandle(action, osrc, self._output_factory, self._echo_factory)
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
        return await self.send_text(
            f"[melobot media: {name if url is None else name + ' at ' + url}]"
        )

    async def send_image(
        self,
        name: str,
        raw: bytes | None = None,
        url: str | None = None,
        mimetype: str | None = None,
    ) -> tuple[ActionHandle, ...]:
        return await self.send_text(
            f"[melobot image: {name if url is None else name + ' at ' + url}]"
        )

    async def send_audio(
        self,
        name: str,
        raw: bytes | None = None,
        url: str | None = None,
        mimetype: str | None = None,
    ) -> tuple[ActionHandle, ...]:
        return await self.send_text(
            f"[melobot audio: {name if url is None else name + ' at ' + url}]"
        )

    async def send_voice(
        self,
        name: str,
        raw: bytes | None = None,
        url: str | None = None,
        mimetype: str | None = None,
    ) -> tuple[ActionHandle, ...]:
        return await self.send_text(
            f"[melobot voice: {name if url is None else name + ' at ' + url}]"
        )

    async def send_video(
        self,
        name: str,
        raw: bytes | None = None,
        url: str | None = None,
        mimetype: str | None = None,
    ) -> tuple[ActionHandle, ...]:
        return await self.send_text(
            f"[melobot video: {name if url is None else name + ' at ' + url}]"
        )

    async def send_file(
        self, name: str, path: str | PathLike[str]
    ) -> tuple[ActionHandle, ...]:
        return await self.send_text(f"[melobot file: {name} at {path}]")

    async def send_refer(
        self, event: Event, contents: Sequence[Content] | None = None
    ) -> tuple[ActionHandle, ...]:
        return await self.send_text(
            f"[melobot refer: {event.__class__.__name__}({event.id})]"
        )

    async def send_resource(self, name: str, url: str) -> tuple[ActionHandle, ...]:
        return await self.send_text(f"[melobot resource: {name} at {url}]")
