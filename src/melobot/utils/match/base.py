from __future__ import annotations

import re
from abc import abstractmethod
from functools import partial

from typing_extensions import Any, Callable, Coroutine, Sequence

from melobot.exceptions import UtilValidateError
from melobot.typ import BetterABC, LogicMode


class Matcher(BetterABC):
    """匹配器基类"""

    def __init__(self) -> None:
        super().__init__()

    def __and__(self, other: Matcher) -> WrappedMatcher:
        if not isinstance(other, Matcher):
            raise UtilValidateError(f"联合匹配器定义时出现了非匹配器对象，其值为：{other}")
        return WrappedMatcher(LogicMode.AND, self, other)

    def __or__(self, other: Matcher) -> WrappedMatcher:
        if not isinstance(other, Matcher):
            raise UtilValidateError(f"联合匹配器定义时出现了非匹配器对象，其值为：{other}")
        return WrappedMatcher(LogicMode.OR, self, other)

    def __invert__(self) -> WrappedMatcher:
        return WrappedMatcher(LogicMode.NOT, self)

    def __xor__(self, other: Matcher) -> WrappedMatcher:
        if not isinstance(other, Matcher):
            raise UtilValidateError(f"联合匹配器定义时出现了非匹配器对象，其值为：{other}")
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
        m2_match: Callable[[], Coroutine[Any, Any, bool]] | None = (
            partial(self.m2.match, text) if self.m2 is not None else None
        )
        return await LogicMode.async_short_calc(self.mode, partial(self.m1.match, text), m2_match)


class StartMatcher(Matcher):
    """字符串起始匹配器"""

    def __init__(self, target: str | Sequence[str], mode: LogicMode = LogicMode.OR) -> None:
        """初始化一个字符串起始匹配器

        `target` 为字符串时，只进行一次起始匹配，即判断是否匹配成功。
        `target` 为字符串序列时，所有字符串都进行起始匹配，再将所有结果使用给定
        `mode` 计算是否匹配成功。

        :param target: 匹配目标
        :param mode: 匹配模式
        """
        super().__init__()
        self.mode = mode
        self.target: set[str] | str
        if not isinstance(target, str):
            self.target = set(target)
        else:
            self.target = target

    async def match(self, text: str) -> bool:
        if isinstance(self.target, str):
            return text.startswith(self.target)
        res_seq = tuple(text.startswith(s) for s in self.target)
        return LogicMode.seq_calc(self.mode, res_seq)


class ContainMatcher(Matcher):
    """字符串包含匹配器"""

    def __init__(self, target: str | Sequence[str], mode: LogicMode = LogicMode.OR) -> None:
        """初始化一个字符串包含匹配器

        `target` 为字符串时，只进行一次包含匹配，即判断是否匹配成功。
        `target` 为字符串序列时，所有字符串都进行包含匹配，再将所有结果使用给定
        `mode` 计算是否匹配成功。

        :param target: 匹配目标
        :param mode: 匹配模式
        """
        super().__init__()
        self.mode = mode
        self.target: set[str] | str
        if not isinstance(target, str):
            self.target = set(target)
        else:
            self.target = target

    async def match(self, text: str) -> bool:
        if isinstance(self.target, str):
            return self.target in text
        res_seq = tuple(s in text for s in self.target)
        return LogicMode.seq_calc(self.mode, res_seq)


class EndMatcher(Matcher):
    """字符串结尾匹配器"""

    def __init__(self, target: str | Sequence[str], mode: LogicMode = LogicMode.OR) -> None:
        """初始化一个字符串结尾匹配器

        `target` 为字符串时，只进行一次结尾匹配，即判断是否匹配成功。
        `target` 为字符串序列时，所有字符串都进行结尾匹配，再将所有结果使用给定
        `mode` 计算是否匹配成功。

        :param target: 匹配目标
        :param mode: 匹配模式
        """
        super().__init__()
        self.mode = mode
        self.target: set[str] | str
        if not isinstance(target, str):
            self.target = set(target)
        else:
            self.target = target

    async def match(self, text: str) -> bool:
        if isinstance(self.target, str):
            return text.endswith(self.target)
        res_seq = tuple(text.endswith(s) for s in self.target)
        return LogicMode.seq_calc(self.mode, res_seq)


class FullMatcher(Matcher):
    """字符串全匹配器"""

    def __init__(self, target: str | Sequence[str], mode: LogicMode = LogicMode.OR) -> None:
        """初始化一个字符串全匹配器

        `target` 为字符串时，只进行一次全匹配，即判断是否匹配成功。
        `target` 为字符串序列时，所有字符串都进行全匹配，再将所有结果使用给定
        `mode` 计算是否匹配成功。

        :param target: 匹配目标
        :param mode: 匹配模式
        """
        super().__init__()
        self.mode = mode
        self.target: set[str] | str
        if not isinstance(target, str):
            self.target = set(target)
        else:
            self.target = target

    async def match(self, text: str) -> bool:
        if isinstance(self.target, str):
            return text == self.target
        res_seq = [text == s for s in self.target]
        return LogicMode.seq_calc(self.mode, res_seq)


class RegexMatcher(Matcher):
    """字符串正则匹配器"""

    def __init__(self, regex_pattern: str, regex_flags: Any = 0) -> None:
        """初始化一个字符串正则匹配器

        :param regex_pattern: 正则 pattern
        :param regex_flags: 正则 flag，默认不使用
        """
        super().__init__()
        self.pattern = regex_pattern
        self.flag = regex_flags

    async def match(self, text: str) -> bool:
        return len(re.findall(self.pattern, text, self.flag)) > 0
