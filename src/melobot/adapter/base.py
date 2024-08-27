from __future__ import annotations

import asyncio
from asyncio import create_task
from contextlib import AsyncExitStack, _GeneratorContextManager, asynccontextmanager
from os import PathLike
from typing import (
    TYPE_CHECKING,
    AsyncGenerator,
    Callable,
    Generic,
    Iterable,
    LiteralString,
    NoReturn,
    TypeVar,
    cast,
)

from typing_extensions import Self

from .._ctx import EventBuildInfo, EventBuildInfoCtx, LoggerCtx, OutSrcFilterCtx
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
from .model import ActionHandle, ActionT, EchoT, EventT

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


async def _input_loop(adapter: Adapter, src: InSourceT) -> NoReturn:
    logger = LoggerCtx().get()
    while True:
        try:
            packet = await src.input()
            event = await adapter.event_factory.create(
                packet
            )  # pylint: disable=no-member
            with _EVENT_BUILD_INFO_CTX.on_ctx(EventBuildInfo(adapter, src)):
                asyncio.create_task(adapter.dispatcher.broadcast(event))
        except Exception:
            logger.exception(f"适配器 {adapter} 处理输入与分发事件时发生异常")
            logger.generic_obj("异常点局部变量：", locals(), level=LogLevel.ERROR)


class Adapter(
    BetterABC,
    Generic[EventFactoryT, OutputFactoryT, EchoFactoryT, InSourceT, OutSourceT],
):
    # pylint: disable=duplicate-code

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

    @asynccontextmanager
    async def launch(self) -> AsyncGenerator[Self, None]:
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
                create_task(_input_loop(self, src))

            self._inited = True
            yield self

    def out_filter(
        self, filter: Callable[[OutSourceT], bool]
    ) -> _GeneratorContextManager[None]:
        return _OUT_SRC_FILTER_CTX.on_ctx(filter)

    def call_output(self, action: ActionT) -> tuple[ActionHandle, ...]:
        osrcs: Iterable[OutSourceT]
        filter = _OUT_SRC_FILTER_CTX.try_get()
        cur_isrc = _EVENT_BUILD_INFO_CTX.get().in_src

        if filter is not None:
            osrcs = (osrc for osrc in self.out_srcs if filter(osrc))
        elif isinstance(cur_isrc, AbstractOutSource):
            osrcs = (cast(OutSourceT, cur_isrc),)
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
