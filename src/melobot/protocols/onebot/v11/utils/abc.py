from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Coroutine

from typing_extensions import Self

from melobot.exceptions import BotException
from melobot.typ import BetterABC, LogicMode, abstractmethod
from melobot.utils import to_async

from ..adapter.event import Event


class UtilsError(BotException): ...


class Cloneable:
    def copy(self) -> Self:
        return deepcopy(self)


class Checker(BetterABC, Cloneable):
    """检查器基类"""

    def __init__(self) -> None:
        super().__init__()

    def __and__(self, other: Checker) -> Checker:
        if not isinstance(other, Checker):
            raise UtilsError(f"联合检查器定义时出现了非检查器对象，其值为：{other}")
        return WrappedChecker(LogicMode.AND, self, other)

    def __or__(self, other: Checker) -> Checker:
        if not isinstance(other, Checker):
            raise UtilsError(f"联合检查器定义时出现了非检查器对象，其值为：{other}")
        return WrappedChecker(LogicMode.OR, self, other)

    def __invert__(self) -> Checker:
        return WrappedChecker(LogicMode.NOT, self)

    def __xor__(self, other: Checker) -> Checker:
        if not isinstance(other, Checker):
            raise UtilsError(f"联合检查器定义时出现了非检查器对象，其值为：{other}")
        return WrappedChecker(LogicMode.XOR, self, other)

    @abstractmethod
    async def check(self, event: Event) -> bool:
        """检查器检查方法

        任何检查器应该实现此抽象方法。

        :param event: 给定的事件
        :return: 检查是否通过
        """
        raise NotImplementedError

    @staticmethod
    def new(func: Callable[[Event], bool]) -> Checker:
        return CustomChecker(func)


class CustomChecker(Checker):
    def __init__(self, func: Callable[[Event], bool]) -> None:
        super().__init__()
        self.func = func

    async def check(self, event: Event) -> bool:
        return self.func(event)


class WrappedChecker(Checker):
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

    async def check(self, event: Event) -> bool:
        c2_check: Callable[[], Coroutine[Any, Any, bool | None]] = (
            (lambda: self.c2.check(event))  # type: ignore[union-attr]
            if self.c2 is not None
            else to_async(lambda: None)  # type: ignore[misc,arg-type]
        )
        return await LogicMode.async_short_calc(
            self.mode, lambda: self.c1.check(event), c2_check
        )


class Matcher(BetterABC, Cloneable):
    """匹配器基类"""

    def __init__(self) -> None:
        super().__init__()

    def __and__(self, other: Matcher) -> WrappedMatcher:
        if not isinstance(other, Matcher):
            raise UtilsError(f"联合匹配器定义时出现了非匹配器对象，其值为：{other}")
        return WrappedMatcher(LogicMode.AND, self, other)

    def __or__(self, other: Matcher) -> WrappedMatcher:
        if not isinstance(other, Matcher):
            raise UtilsError(f"联合匹配器定义时出现了非匹配器对象，其值为：{other}")
        return WrappedMatcher(LogicMode.OR, self, other)

    def __invert__(self) -> WrappedMatcher:
        return WrappedMatcher(LogicMode.NOT, self)

    def __xor__(self, other: Matcher) -> WrappedMatcher:
        if not isinstance(other, Matcher):
            raise UtilsError(f"联合匹配器定义时出现了非匹配器对象，其值为：{other}")
        return WrappedMatcher(LogicMode.XOR, self, other)

    @abstractmethod
    async def match(self, text: str) -> bool:
        """匹配器匹配方法

        任何匹配器应该实现此抽象方法。

        :param text: 消息事件的文本内容
        :return: 是否匹配
        """
        raise NotImplementedError


class WrappedMatcher(Matcher):
    """合并匹配器

    在两个 :class:`Matcher` 对象间使用 | & ^ ~ 运算符即可返回合并匹配器
    """

    def __init__(
        self,
        mode: LogicMode,
        matcher1: Matcher,
        matcher2: Matcher | None = None,
    ) -> None:
        """初始化一个合并匹配器

        :param mode: 合并匹配的逻辑模式
        :param matcher1: 匹配器1
        :param matcher2: 匹配器2
        """
        super().__init__()
        self.mode = mode
        self.m1, self.m2 = matcher1, matcher2

    async def match(self, text: str) -> bool:
        m2_match: Callable[[], Coroutine[Any, Any, bool | None]] = (
            (lambda: self.m2.match(text))  # type: ignore[union-attr]
            if self.m2 is not None
            else to_async(lambda: None)  # type: ignore[misc,arg-type]
        )
        return await LogicMode.async_short_calc(
            self.mode, lambda: self.m1.match(text), m2_match
        )


@dataclass
class ParseArgs:
    """解析参数"""

    name: str
    vals: list[Any]


class Parser(BetterABC):
    """解析器基类

    解析器一般用作从消息文本中按规则批量提取参数
    """

    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    async def parse(self, text: str) -> ParseArgs | None:
        """解析方法

        任何解析器应该实现此抽象方法

        :param text: 消息文本内容
        :return: 解析结果

        """
        raise NotImplementedError
