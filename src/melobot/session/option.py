from __future__ import annotations

from typing import Callable, Generic

from ..adapter.base import EventT
from ..typ import AsyncCallable, BetterABC, abstractmethod


class Rule(BetterABC, Generic[EventT]):
    @staticmethod
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


class SessionOption(Generic[EventT]):
    def __init__(
        self,
        rule: Rule[EventT] | Callable[[EventT, EventT], bool] | None = None,
        wait: bool = True,
        nowait_cb: AsyncCallable[[], None] | None = None,
        keep: bool = False,
    ) -> None:
        super().__init__()
        if rule is None:
            self.rule = None
        else:
            self.rule = rule if isinstance(rule, Rule) else Rule.new(rule)
        self.wait = wait
        self.nowait_cb = nowait_cb
        self.keep = keep
