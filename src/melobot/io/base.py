import time
from dataclasses import dataclass, field
from enum import Enum
from types import TracebackType
from typing import Any, Callable, Generic

from typing_extensions import LiteralString, Self, TypeVar

from .._hook import HookBus
from ..typ import AsyncCallable, BetterABC, P, abstractmethod
from ..utils import get_id


@dataclass(frozen=True)
class _Packet:
    time: float = field(default_factory=lambda: time.time_ns() / 1e9)
    id: str = field(default_factory=get_id)
    protocol: LiteralString | None = None
    data: Any = None


@dataclass(frozen=True)
class InPacket(_Packet):
    pass


@dataclass(frozen=True)
class OutPacket(_Packet):
    pass


@dataclass(frozen=True)
class EchoPacket(_Packet):
    ok: bool = True
    status: int = 0
    prompt: str = ""
    noecho: bool = False


InPacketT = TypeVar("InPacketT", bound=InPacket)
OutPacketT = TypeVar("OutPacketT", bound=OutPacket)
EchoPacketT = TypeVar("EchoPacketT", bound=EchoPacket)


class SourceLifeSpan(Enum):
    STARTED = "sta"
    STOPPED = "sto"


class AbstractSource(BetterABC):
    def __init__(self, protocol: LiteralString) -> None:
        self.protocol = protocol

        self._life_bus = HookBus[SourceLifeSpan](SourceLifeSpan)

    @abstractmethod
    async def open(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def opened(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError

    async def __aenter__(self) -> Self:
        if self.opened():
            return self

        await self.open()
        await self._life_bus.emit(SourceLifeSpan.STARTED)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if not self.opened():
            return None

        try:
            await self.close()
        finally:
            await self._life_bus.emit(SourceLifeSpan.STOPPED, wait=True)
        return None

    def on(
        self, *period: SourceLifeSpan
    ) -> Callable[[AsyncCallable[P, None]], AsyncCallable[P, None]]:
        def wrapped(func: AsyncCallable[P, None]) -> AsyncCallable[P, None]:
            for type in period:
                self._life_bus.register(type, func)
            return func

        return wrapped


class AbstractInSource(AbstractSource, BetterABC, Generic[InPacketT]):
    @abstractmethod
    async def open(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def opened(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def input(self) -> InPacketT:
        raise NotImplementedError


InSourceT = TypeVar("InSourceT", bound=AbstractInSource)


class AbstractOutSource(AbstractSource, BetterABC, Generic[OutPacketT, EchoPacketT]):
    @abstractmethod
    async def open(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def opened(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def output(self, packet: OutPacketT) -> EchoPacketT:
        raise NotImplementedError


OutSourceT = TypeVar("OutSourceT", bound=AbstractOutSource)

InOrOutSourceT = TypeVar("InOrOutSourceT", bound=AbstractInSource | AbstractOutSource)


class AbstractIOSource(
    AbstractInSource[InPacketT], AbstractOutSource[OutPacketT, EchoPacketT], BetterABC
):
    @abstractmethod
    async def open(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def opened(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def input(self) -> InPacketT:
        raise NotImplementedError

    @abstractmethod
    async def output(self, packet: OutPacketT) -> EchoPacketT:
        raise NotImplementedError


IOSourceT = TypeVar("IOSourceT", bound=AbstractIOSource)
