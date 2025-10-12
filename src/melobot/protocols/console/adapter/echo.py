from __future__ import annotations

from typing_extensions import Any, Generic

from melobot.adapter import Echo as RootEcho

from ..const import PROTOCOL_IDENTIFIER
from ..io.model import EchoDataT


class Echo(RootEcho, Generic[EchoDataT]):
    def __init__(self, data: EchoDataT) -> None:
        super().__init__(protocol=PROTOCOL_IDENTIFIER)
        self.type = data.type
        self.raw = data
        self.content = data.content

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(type={self.type})"

    def result(self) -> Any:
        if self.content is None:
            raise ValueError("回应中的响应内容为空")
        return self.content

    @classmethod
    def resolve(cls, data: EchoDataT) -> Echo:
        match data.type:
            case _:
                return cls(data)
