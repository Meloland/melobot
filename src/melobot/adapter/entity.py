import time

from ..typing import (
    Any,
    BetterABC,
    LiteralString,
    NamedTuple,
    Optional,
    Sequence,
    TypeVar,
    abstractattr,
)
from ..utils import get_id
from .content import AbstractContent


class AbstractEntity(BetterABC):
    type: str | None = abstractattr()
    time: int = abstractattr()
    id: str = abstractattr()
    protocol: LiteralString | None = abstractattr()
    scope: Optional[NamedTuple] = abstractattr()


class BaseEvent(AbstractEntity):
    def __init__(
        self,
        type: str | None = None,
        time: int = time.time_ns(),
        id: str = get_id(),
        protocol: LiteralString | None = None,
        scope: Optional[NamedTuple] = None,
        contents: Sequence[AbstractContent] = (),
    ) -> None:
        self.type = type
        self.time = time
        self.id = id
        self.protocol = protocol
        self.contents = contents
        self.scope = scope


class BaseAction(AbstractEntity):
    def __init__(
        self,
        type: str | None = None,
        time: int = time.time_ns(),
        id: str = get_id(),
        protocol: LiteralString | None = None,
        scope: Optional[NamedTuple] = None,
        contents: Sequence[AbstractContent] = (),
    ) -> None:
        self.type = type
        self.time = time
        self.id = id
        self.protocol = protocol
        self.contents = contents
        self.scope = scope


class BaseEcho(AbstractEntity):
    def __init__(
        self,
        type: str | None = None,
        time: int = time.time_ns(),
        id: str = get_id(),
        protocol: LiteralString | None = None,
        scope: Optional[NamedTuple] = None,
        ok: bool = True,
        status: int = 0,
        prompt: str = "",
        data: Any = None,
    ) -> None:
        self.type = type
        self.time = time
        self.id = id
        self.protocol = protocol
        self.scope = scope
        self.ok = ok
        self.status = status
        self.prompt = prompt
        self.data = data


Event_T = TypeVar("Event_T", bound=BaseEvent)
Action_T = TypeVar("Action_T", bound=BaseAction)
Echo_T = TypeVar("Echo_T", bound=BaseEcho)
