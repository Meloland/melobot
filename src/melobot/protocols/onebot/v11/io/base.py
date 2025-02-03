from abc import abstractmethod

from melobot.io import AbstractInSource, AbstractIOSource, AbstractOutSource

from ..const import PROTOCOL_IDENTIFIER
from .packet import EchoPacket, InPacket, OutPacket


class BaseInSource(AbstractInSource[InPacket]):
    def __init__(self) -> None:
        super().__init__(PROTOCOL_IDENTIFIER)

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


class BaseOutSource(AbstractOutSource[OutPacket, EchoPacket]):
    def __init__(self) -> None:
        super().__init__(PROTOCOL_IDENTIFIER)

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


class BaseIOSource(AbstractIOSource[InPacket, OutPacket, EchoPacket]):
    """

    :ivar float cd_time: 发送行为操作的冷却时间（防风控）
    """

    # pylint: disable=duplicate-code
    def __init__(self, cd_time: float) -> None:
        super().__init__(PROTOCOL_IDENTIFIER)
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
