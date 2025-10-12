from __future__ import annotations

from typing_extensions import Generic, cast

from melobot.adapter import Event as RootEvent
from melobot.adapter import TextEvent as RootTextEvent
from melobot.adapter import content

from ..const import PROTOCOL_IDENTIFIER
from ..io.model import InputData, InputDataT, InputType, StdinInputData


class Event(RootEvent, Generic[InputDataT]):
    def __init__(self, data: InputData) -> None:
        super().__init__(PROTOCOL_IDENTIFIER)
        self.type = data.type
        self.raw = data

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(type={self.type})"

    @classmethod
    def resolve(cls, data: InputDataT) -> Event:
        if data.type is InputType.STDIN:
            return StdinEvent.resolve(cast(StdinInputData, data))
        return cls(data)

    def is_stdin(self) -> bool:
        return self.type is InputType.STDIN


class StdinEvent(RootTextEvent, Event[StdinInputData]):
    def __init__(self, data: StdinInputData) -> None:
        super().__init__(data)
        self.text = data.content
        self.textlines = self.text.split("\n")
        self.contents = (content.TextContent(self.text),)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.text!r})"

    @classmethod
    def resolve(cls, data: StdinInputData) -> StdinEvent:
        return cls(data)
