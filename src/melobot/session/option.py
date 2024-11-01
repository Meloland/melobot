from __future__ import annotations

from typing import Callable, Generic, final

from ..adapter.model import EventT
from ..typ import BetterABC, abstractmethod


class Rule(BetterABC, Generic[EventT]):
    """会话规则

    对于更复杂的情况，可以继承此类，在子类中结合状态信息实现更动态的会话判断
    """

    @staticmethod
    @final
    def new(meth: Callable[[EventT, EventT], bool]) -> Rule[EventT]:
        """从可调用对象创建一个新的会话规则对象

        :param meth: 用于会话判断的可调用对象
        :return: 会话规则
        """
        return _CustomRule[EventT](meth)

    @abstractmethod
    async def compare(self, e1: EventT, e2: EventT) -> bool:
        """会话判断的方法

        :param e1: 事件 1
        :param e2: 事件 2
        :return: 为 `True` 则在一个会话中，反之亦然
        """
        raise NotImplementedError


class _CustomRule(Rule[EventT]):
    def __init__(self, meth: Callable[[EventT, EventT], bool]) -> None:
        super().__init__()
        self.meth = meth

    async def compare(self, e1: EventT, e2: EventT) -> bool:
        return self.meth(e1, e2)
