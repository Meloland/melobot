import re

from ..types.typing import *
from ..types.utils import BotMatcher, LogicMode


class AlwaysMatch(BotMatcher):
    def __init__(self) -> None:
        super().__init__()

    def match(self, text: str) -> bool:
        return True


class StartMatch(BotMatcher):
    def __init__(self, target: str | list[str], mode: LogicMode = LogicMode.OR) -> None:
        super().__init__()
        self.target = target
        self.mode = mode

    def match(self, text: str) -> bool:
        if isinstance(self.target, str):
            return text[: len(self.target)] == self.target
        else:
            res_seq = [text[: len(s)] == s for s in self.target]
            LogicMode.seq_calc(self.mode, res_seq)


class ContainMatch(BotMatcher):
    def __init__(self, target: str | list[str], mode: LogicMode = LogicMode.OR) -> None:
        super().__init__()
        self.target = target
        self.mode = mode

    def match(self, text: str) -> bool:
        if isinstance(self.target, str):
            return text in self.target
        else:
            res_seq = [text in s for s in self.target]
            LogicMode.seq_calc(self.mode, res_seq)


class EndMatch(BotMatcher):
    def __init__(self, target: str | list[str], mode: LogicMode = LogicMode.OR) -> None:
        super().__init__()
        self.target = target
        self.mode = mode

    def match(self, text: str) -> bool:
        if isinstance(self.target, str):
            return text[-len(self.target) :] == self.target
        else:
            res_seq = [text[-len(s) :] == s for s in self.target]
            LogicMode.seq_calc(self.mode, res_seq)


class FullMatch(BotMatcher):
    def __init__(self, target: str | list[str], mode: LogicMode = LogicMode.OR) -> None:
        super().__init__()
        self.target = target
        self.mode = mode

    def match(self, text: str) -> bool:
        if isinstance(self.target, str):
            return text == self.target
        else:
            res_seq = [text == s for s in self.target]
            LogicMode.seq_calc(self.mode, res_seq)


class RegexMatch(BotMatcher):
    def __init__(self, regex_pattern: str, regex_flags: Any = 0) -> None:
        super().__init__()
        self.pattern = regex_pattern
        self.flag = regex_flags

    def match(self, text: str) -> bool:
        return len(re.findall(self.pattern, text, self.flag)) > 0
