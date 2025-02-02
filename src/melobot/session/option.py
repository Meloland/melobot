from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import TYPE_CHECKING, Any, Callable, Generic, final

from ..adapter.model import EventT
from ..typ.cls import BetterABC

if TYPE_CHECKING:
    from .base import Session


@dataclass
class CompareInfo(Generic[EventT]):
    """用于会话判断的信息"""

    session: "Session"
    old_event: EventT
    new_event: EventT


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

    async def compare(self, e1: EventT, e2: EventT) -> bool:
        """会话判断的方法

        抽象方法，和 :meth:`compare_with` 二选一实现

        :param e1: 某一已存在的会话中的事件
        :param e2: 待判断的事件
        :return: 为 `True` 则在一个会话中，反之亦然
        """
        raise NotImplementedError

    async def compare_with(self, info: CompareInfo[EventT]) -> bool:
        """会话判断的方法

        抽象方法，和 :meth:`compare` 二选一实现

        :param info: 用于会话判断的信息
        :return: 为 `True` 则在一个会话中，反之亦然
        """
        raise NotImplementedError

    async def __default_compare_with__(self, info: CompareInfo[EventT]) -> bool:
        return await self.compare(info.old_event, info.new_event)

    def __init_subclass__(cls, *args: Any, **kwargs: Any) -> None:
        super().__init_subclass__(*args, **kwargs)
        has_comp = cls.compare is not Rule.compare
        has_comp_with = cls.compare_with is not Rule.compare_with

        if has_comp_with:
            return
        if has_comp:
            cls.compare_with = cls.__default_compare_with__  # type: ignore[method-assign]
            return

        raise TypeError(
            f"{cls.__name__} 类必须实现抽象方法"
            f"'{cls.compare.__name__}', '{cls.compare_with.__name__}' 其中之一"
        ) from None


class _CustomRule(Rule[EventT]):
    # pylint: disable=abstract-method
    def __init__(self, meth: Callable[[EventT, EventT], bool]) -> None:
        super().__init__()
        self.meth = meth

    async def compare(self, e1: EventT, e2: EventT) -> bool:
        return self.meth(e1, e2)
