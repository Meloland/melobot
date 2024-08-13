from ..adapter.base import Event_T
from ..typ import AsyncCallable, BetterABC, Callable, Generic, abstractmethod


class AbstractRule(BetterABC, Generic[Event_T]):
    def __init__(self) -> None:
        super().__init__()

    @staticmethod
    def new(meth: Callable[[Event_T, Event_T], bool]) -> "AbstractRule[Event_T]":
        return _CustomRule[Event_T](meth)

    @abstractmethod
    async def compare(self, e1: Event_T, e2: Event_T) -> bool:
        raise NotImplementedError


class _CustomRule(AbstractRule[Event_T]):
    def __init__(self, meth: Callable[[Event_T, Event_T], bool]) -> None:
        super().__init__()
        self.meth = meth

    async def compare(self, e1: Event_T, e2: Event_T) -> bool:
        return self.meth(e1, e2)


class SessionOption(Generic[Event_T]):
    def __init__(
        self,
        rule: AbstractRule[Event_T] | Callable[[Event_T, Event_T], bool] | None = None,
        wait: bool = True,
        nowait_cb: AsyncCallable[[], None] | None = None,
        keep: bool = False,
    ) -> None:
        super().__init__()
        if rule is None:
            self.rule = None
        else:
            self.rule = rule if isinstance(rule, AbstractRule) else AbstractRule.new(rule)
        self.wait = wait
        self.nowait_cb = nowait_cb
        self.keep = keep
