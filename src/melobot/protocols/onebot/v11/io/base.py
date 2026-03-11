from abc import abstractmethod

from typing_extensions import Any, Self

from melobot.io import AbstractIOSource

from ..const import PROTOCOL_IDENTIFIER
from .packet import EchoPacket, InPacket, OutPacket


class BaseIOSource(AbstractIOSource[InPacket, OutPacket, EchoPacket]):
    """

    :ivar float cd_time: 发送行为操作的冷却时间（防风控）
    """

    def __init__(self, cd_time: float) -> None:
        super().__init__()
        self.protocol = PROTOCOL_IDENTIFIER
        self.cd_time = cd_time if cd_time >= 0 else 0
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

    @abstractmethod
    async def input(self) -> InPacket:
        raise NotImplementedError

    @abstractmethod
    async def output(self, packet: OutPacket) -> EchoPacket:
        raise NotImplementedError


class InstCounter:
    INSTANCE_COUNT = 0

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        o = super().__new__(cls)
        cls.INSTANCE_COUNT += 1
        return o
