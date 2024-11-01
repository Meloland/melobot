from melobot.io import AbstractIOSource
from melobot.log import GenericLogger, get_logger
from melobot.typ import abstractmethod

from ..const import PROTOCOL_IDENTIFIER
from .packet import EchoPacket, InPacket, OutPacket


class BaseIO(AbstractIOSource[InPacket, OutPacket, EchoPacket]):
    """

    :ivar float cd_time: 发送行为操作的冷却时间（防风控）
    """

    # pylint: disable=duplicate-code
    def __init__(self, cd_time: float) -> None:
        super().__init__(PROTOCOL_IDENTIFIER)
        self.cd_time = cd_time

    @property
    def logger(self) -> GenericLogger:
        return get_logger()

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
