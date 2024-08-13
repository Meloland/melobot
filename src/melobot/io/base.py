import asyncio
import time
from dataclasses import dataclass, field

from ..typ import (
    Any,
    BetterABC,
    Generic,
    LiteralString,
    Self,
    TracebackType,
    TypeVar,
    abstractattr,
    abstractmethod,
)
from ..utils import get_id


@dataclass(kw_only=True, frozen=True)
class _Packet:
    time: int = field(default_factory=time.time_ns)
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


InPacket_T = TypeVar("InPacket_T", bound=InPacket)
OutPacket_T = TypeVar("OutPacket_T", bound=OutPacket)
EchoPacket_T = TypeVar("EchoPacket_T", bound=EchoPacket)


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
        else:
            return False


class AbstractInSource(AbstractSource, Generic[InPacket_T]):
    @abstractmethod
    async def input(self) -> InPacket_T:
        raise NotImplementedError


InSource_T = TypeVar("InSource_T", bound=AbstractInSource)


class AbstractOutSource(AbstractSource, Generic[OutPacket_T, EchoPacket_T]):
    @abstractmethod
    async def output(self, packet: OutPacket_T) -> EchoPacket_T:
        raise NotImplementedError


OutSource_T = TypeVar("OutSource_T", bound=AbstractOutSource)


class AbstractIOSource(
    AbstractInSource[InPacket_T], AbstractOutSource[OutPacket_T, EchoPacket_T]
): ...
