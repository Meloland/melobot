from ..io.abc import EchoPacket_T, InputPacket_T, OutputPacket_T
from ..typing import BetterABC, Generic, LiteralString, abstractattr, abstractmethod
from .content import AbstractContent
from .entity import Action_T, BaseAction, BaseEcho, BaseEvent, Echo_T, Event_T

__all__ = (
    "AbstractAdapter",
    "AbstractEventFactory",
    "AbstractActionFactory",
    "AbstractEchoFactory",
    "BaseEvent",
    "BaseAction",
    "BaseEcho",
    "Event_T",
    "Action_T",
    "Echo_T",
    "AbstractContent",
)


class AbstractEventFactory(BetterABC, Generic[InputPacket_T, Event_T]):
    @abstractmethod
    def create(self, packet: InputPacket_T) -> Event_T:
        raise NotImplementedError


class AbstractActionFactory(BetterABC, Generic[Action_T, OutputPacket_T]):
    @abstractmethod
    def create(self, action: Action_T) -> OutputPacket_T:
        raise NotImplementedError


class AbstractEchoFactory(BetterABC, Generic[EchoPacket_T, Echo_T]):
    @abstractmethod
    def create(self, packet: EchoPacket_T) -> Echo_T:
        raise NotImplementedError


class AbstractAdapter(BetterABC):
    protocol: LiteralString = abstractattr()
    event_factory: AbstractEventFactory = abstractattr()
    action_factory: AbstractActionFactory = abstractattr()
    echo_factory: AbstractEchoFactory = abstractattr()
