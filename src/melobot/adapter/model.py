from ..io.abc import EchoPacket_T, InputPacket_T, OutputPacket_T
from ..typing import (
    Any,
    BetterABC,
    Generic,
    NamedTuple,
    Optional,
    Sequence,
    TypeVar,
    abstractattr,
    abstractmethod,
)
from .content import AbstractContent


class AbstractEntity(BetterABC):
    type: str = abstractattr()
    time: int = abstractattr()
    id: str = abstractattr()
    protocol: str | None = abstractattr()
    scope: Optional[NamedTuple] = abstractattr()


class AbstractEvent(AbstractEntity):
    contents: Sequence[AbstractContent] = abstractattr()


class AbstractAction(AbstractEntity):
    contents: Sequence[AbstractContent] = abstractattr()


class AbstractEcho(AbstractEntity):
    ok: bool = abstractattr()
    status: int = abstractattr()
    prompt: str = abstractattr()
    data: Any = abstractattr()


Event_T = TypeVar("Event_T", bound=AbstractEvent)
Action_T = TypeVar("Action_T", bound=AbstractAction)
Echo_T = TypeVar("Echo_T", bound=AbstractEcho)


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
