import re
from typing import Any

from melobot.typ import LogicMode

from .abc import Matcher


class StartMatcher(Matcher):
    """字符串起始匹配器"""

    def __init__(self, target: str | list[str], mode: LogicMode = LogicMode.OR) -> None:
        """初始化一个字符串起始匹配器

        `target` 为字符串时，只进行一次起始匹配，即判断是否匹配成功。
        `target` 为字符串列表时，所有字符串都进行起始匹配，再将所有结果使用给定
        `mode` 计算是否匹配成功。

        :param target: 匹配目标
        :param mode: 匹配模式
        """
        super().__init__()
        self.target = target
        self.mode = mode

    async def match(self, text: str) -> bool:
        if isinstance(self.target, str):
            return text[: len(self.target)] == self.target
        res_seq = [text[: len(s)] == s for s in self.target]
        return LogicMode.seq_calc(self.mode, res_seq)


class ContainMatcher(Matcher):
    """字符串包含匹配器"""

    def __init__(self, target: str | list[str], mode: LogicMode = LogicMode.OR) -> None:
        """初始化一个字符串包含匹配器

        `target` 为字符串时，只进行一次包含匹配，即判断是否匹配成功。
        `target` 为字符串列表时，所有字符串都进行包含匹配，再将所有结果使用给定
        `mode` 计算是否匹配成功。

        :param target: 匹配目标
        :param mode: 匹配模式
        """
        super().__init__()
        self.target = target
        self.mode = mode

    async def match(self, text: str) -> bool:
        if isinstance(self.target, str):
            return self.target in text
        res_seq = [s in text for s in self.target]
        return LogicMode.seq_calc(self.mode, res_seq)


class EndMatcher(Matcher):
    """字符串结尾匹配器"""

    def __init__(self, target: str | list[str], mode: LogicMode = LogicMode.OR) -> None:
        """初始化一个字符串结尾匹配器

        `target` 为字符串时，只进行一次结尾匹配，即判断是否匹配成功。
        `target` 为字符串列表时，所有字符串都进行结尾匹配，再将所有结果使用给定
        `mode` 计算是否匹配成功。

        :param target: 匹配目标
        :param mode: 匹配模式
        """
        super().__init__()
        self.target = target
        self.mode = mode

    async def match(self, text: str) -> bool:
        if isinstance(self.target, str):
            return text[-len(self.target) :] == self.target
        res_seq = [text[-len(s) :] == s for s in self.target]
        return LogicMode.seq_calc(self.mode, res_seq)


class FullMatcher(Matcher):
    """字符串全匹配器"""

    def __init__(self, target: str | list[str], mode: LogicMode = LogicMode.OR) -> None:
        """初始化一个字符串全匹配器

        `target` 为字符串时，只进行一次全匹配，即判断是否匹配成功。
        `target` 为字符串列表时，所有字符串都进行全匹配，再将所有结果使用给定
        `mode` 计算是否匹配成功。

        :param target: 匹配目标
        :param mode: 匹配模式
        """
        super().__init__()
        self.target = target
        self.mode = mode

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
