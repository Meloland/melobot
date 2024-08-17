import asyncio
import time
from dataclasses import dataclass, field
from types import TracebackType
from typing import Any, Generic, LiteralString, TypeVar

from typing_extensions import Self

from ..typ import BetterABC, abstractattr, abstractmethod
from ..utils import get_id


@dataclass(kw_only=True, frozen=True)
class _Packet:
    time: float = field(default_factory=lambda: time.time_ns() / 1e9)
    id: str = field(default_factory=get_id)
    protocol: LiteralString | None = None
    data: Any = None


@dataclass(kw_only=True, frozen=True)
class InPacket(_Packet):
    pass


@dataclass(kw_only=True, frozen=True)
class OutPacket(_Packet):
    pass


@dataclass(kw_only=True, frozen=True)
class EchoPacket(_Packet):
    ok: bool = True
    status: int = 0
    prompt: str = ""
    noecho: bool = False


InPacketT = TypeVar("InPacketT", bound=InPacket)
OutPacketT = TypeVar("OutPacketT", bound=OutPacket)
EchoPacketT = TypeVar("EchoPacketT", bound=EchoPacket)


class AbstractSource(BetterABC):
    protocol: LiteralString = abstractattr()

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
        await self.open()
        return self

    async def __aexit__(
        self, exc_type: type[Exception], exc_val: Exception, exc_tb: TracebackType
    ) -> bool:
        await self.close()
        if exc_type in (None, asyncio.CancelledError):
            return True
        return False


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


class AbstractIOSource(
    AbstractInSource[InPacketT], AbstractOutSource[OutPacketT, EchoPacketT], BetterABC
):
    async def open(self) -> None:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError

    def opened(self) -> bool:
        raise NotImplementedError

    async def input(self) -> InPacketT:
        raise NotImplementedError

    async def output(self, packet: OutPacketT) -> EchoPacketT:
        raise NotImplementedError
