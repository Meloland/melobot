from __future__ import annotations

from typing import Callable, Generic, final

from ..adapter.model import EventT
from ..typ import BetterABC, abstractmethod


class Rule(BetterABC, Generic[EventT]):
    @staticmethod
    @final
    def new(meth: Callable[[EventT, EventT], bool]) -> Rule[EventT]:
        return _CustomRule[EventT](meth)

    @abstractmethod
    async def compare(self, e1: EventT, e2: EventT) -> bool:
        raise NotImplementedError


class _CustomRule(Rule[EventT]):
    def __init__(self, meth: Callable[[EventT, EventT], bool]) -> None:
        super().__init__()
        self.meth = meth

    async def compare(self, e1: EventT, e2: EventT) -> bool:
        return self.meth(e1, e2)
