import asyncio
import time
from dataclasses import dataclass

from typing_extensions import Self

from ..typing import (
    Any,
    BetterABC,
    Generic,
    LiteralString,
    TracebackType,
    TypeVar,
    abstractmethod,
)
from ..utils import get_id


@dataclass(kw_only=True)
class GenericPacket:
    time: int = time.time_ns()
    id: str = get_id()
    protocol: LiteralString | None = None
    data: Any = None


@dataclass(kw_only=True)
class GenericOutputPacket(GenericPacket):
    echo: bool = True


@dataclass(kw_only=True)
class GenericEchoPacket(GenericPacket):
    ok: bool = True
    status: int = 0
    prompt: str = ""
    notset: bool = False


GenericInputPacket = GenericPacket
InputPacket_T = TypeVar("InputPacket_T", bound=GenericInputPacket)
OutputPacket_T = TypeVar("OutputPacket_T", bound=GenericOutputPacket)
EchoPacket_T = TypeVar("EchoPacket_T", bound=GenericEchoPacket)


class AbstractSource(BetterABC):
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


class AbstractInSource(AbstractSource, Generic[InputPacket_T]):
    @abstractmethod
    async def input(self) -> InputPacket_T:
        raise NotImplementedError


class AbstractOutSource(AbstractSource, Generic[OutputPacket_T, EchoPacket_T]):
    @abstractmethod
    async def output(self, packet: OutputPacket_T) -> EchoPacket_T:
        raise NotImplementedError


class AbstractIOSource(
    AbstractInSource[InputPacket_T], AbstractOutSource[OutputPacket_T, EchoPacket_T]
): ...


class GenericIOSource(
    AbstractIOSource[GenericPacket, GenericOutputPacket, GenericEchoPacket]
): ...
