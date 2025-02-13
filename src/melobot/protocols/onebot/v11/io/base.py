from abc import abstractmethod

from melobot.io import (
    AbstractInSource,
    AbstractIOSource,
    AbstractOutSource,
    AbstractSource,
)

from ..const import PROTOCOL_IDENTIFIER
from .packet import EchoPacket, InPacket, OutPacket


class BaseSource(AbstractSource):
    def __init__(self) -> None:
        super().__init__()
        self.protocol = PROTOCOL_IDENTIFIER
        self._hook_bus.set_tag(f"{self.protocol}/{self.__class__.__name__}")

    @abstractmethod
    async def open(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def opened(self) -> bool:
        raise NotImplementedError


class BaseInSource(AbstractInSource[InPacket], BaseSource):
    def __init__(self) -> None:
        super().__init__()

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
    async def input(self) -> InPacket:
        raise NotImplementedError


class BaseOutSource(AbstractOutSource[OutPacket, EchoPacket], BaseSource):
    def __init__(self) -> None:
        super().__init__()

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
    async def output(self, packet: OutPacket) -> EchoPacket:
        raise NotImplementedError


class BaseIOSource(AbstractIOSource[InPacket, OutPacket, EchoPacket], BaseInSource, BaseOutSource):
    """

    :ivar float cd_time: 发送行为操作的冷却时间（防风控）
    """

    def __init__(self, cd_time: float) -> None:
        super().__init__()
        self.cd_time = cd_time if cd_time >= 0 else 0

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
    async def input(self) -> InPacket:
        raise NotImplementedError

    @abstractmethod
    async def output(self, packet: OutPacket) -> EchoPacket:
        raise NotImplementedError
