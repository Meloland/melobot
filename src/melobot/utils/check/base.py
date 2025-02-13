from __future__ import annotations

from abc import abstractmethod
from functools import partial

from typing_extensions import Any, Callable, Coroutine, Generic

from ...adapter.model import EventT
from ...exceptions import UtilValidateError
from ...typ._enum import LogicMode
from ...typ.base import SyncOrAsyncCallable
from ...typ.cls import BetterABC
from ..base import to_async


class Checker(Generic[EventT], BetterABC):
    """检查器基类"""

    def __init__(self, fail_cb: SyncOrAsyncCallable[[], None] | None = None) -> None:
        super().__init__()
        self.fail_cb = to_async(fail_cb) if fail_cb is not None else None

    def __and__(self, other: Checker) -> WrappedChecker:
        if not isinstance(other, Checker):
            raise UtilValidateError(f"联合检查器定义时出现了非检查器对象，其值为：{other}")
        return WrappedChecker(LogicMode.AND, self, other)

    def __or__(self, other: Checker) -> WrappedChecker:
        if not isinstance(other, Checker):
            raise UtilValidateError(f"联合检查器定义时出现了非检查器对象，其值为：{other}")
        return WrappedChecker(LogicMode.OR, self, other)

    def __invert__(self) -> WrappedChecker:
        return WrappedChecker(LogicMode.NOT, self)

    def __xor__(self, other: Checker) -> WrappedChecker:
        if not isinstance(other, Checker):
            raise UtilValidateError(f"联合检查器定义时出现了非检查器对象，其值为：{other}")
        return WrappedChecker(LogicMode.XOR, self, other)

    @abstractmethod
    async def check(self, event: EventT) -> bool:
        """检查器检查方法

        任何检查器应该实现此抽象方法。

        :param event: 给定的事件
        :return: 检查是否通过
        """
        raise NotImplementedError

    @staticmethod
    def new(func: Callable[[EventT], bool]) -> Checker[EventT]:
        return _CustomChecker[EventT](func)


class _CustomChecker(Checker[EventT]):
    def __init__(self, func: Callable[[EventT], bool]) -> None:
        super().__init__()
        self.func = func

    async def check(self, event: EventT) -> bool:
        return self.func(event)


class WrappedChecker(Checker[EventT]):
    """合并检查器

    在两个 :class:`Checker` 对象间使用 | & ^ ~ 运算符即可返回合并检查器。
    """

    def __init__(
        self,
        mode: LogicMode,
        checker1: Checker,
        checker2: Checker | None = None,
    ) -> None:
        """初始化一个合并检查器

        :param mode: 合并检查的逻辑模式
        :param checker1: 检查器1
        :param checker2: 检查器2
        """
        super().__init__()
        self.mode = mode
        self.c1, self.c2 = checker1, checker2

    def set_fail_cb(self, fail_cb: SyncOrAsyncCallable[[], None] | None) -> None:
        self.fail_cb = to_async(fail_cb) if fail_cb is not None else None

    async def check(self, event: EventT) -> bool:
        c2_check: Callable[[], Coroutine[Any, Any, bool]] | None = (
            partial(self.c2.check, event) if self.c2 is not None else None
        )
        status = await LogicMode.async_short_calc(
            self.mode, partial(self.c1.check, event), c2_check
        )

        if not status and self.fail_cb is not None:
            await self.fail_cb()
        return status


def checker_join(*checkers: Checker | None | Callable[[Any], bool]) -> Checker:
    """合并检查器

    相比于使用 | & ^ ~ 运算符，此函数可以接受一个检查器序列，并返回一个合并检查器。
    检查器序列可以为检查器对象，检查函数或空值

    :return: 合并后的检查器对象
    """
    checker: Checker | None = None
    for c in checkers:
        if c is None:
            continue
        if isinstance(c, Checker):
            checker = checker & c if checker else c
        else:
            checker = checker & Checker.new(c) if checker else Checker.new(c)

    if checker is None:
        raise ValueError("检查器序列不能全为空")
    return checker
