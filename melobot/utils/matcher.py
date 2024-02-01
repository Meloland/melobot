import re

from ..types.typing import *
from ..types.utils import BotMatcher


class StartMatch(BotMatcher):
    def __init__(self, target: str) -> None:
        super().__init__()
        self.target = target

    def match(self, text: str) -> bool:
        return text[:len(self.target)] == self.target


class ContainMatch(BotMatcher):
    def __init__(self, target: str, freq: int=1) -> None:
        super().__init__()
        self.target = target
        self.freq = freq

    def match(self, text: str) -> bool:
        if self.freq == 1:
            return self.target in text
        else:
            return len(re.findall(self.target, text)) == self.freq


class EndMatch(BotMatcher):
    def __init__(self, target: str) -> None:
        super().__init__()
        self.target = target

    def match(self, text: str) -> bool:
        return text[-len(self.target):-1] == self.target


class FullMatch(BotMatcher):
    def __init__(self, target: str) -> None:
        super().__init__()
        self.target = target

    def match(self, text: str) -> bool:
        return text == self.target


class RegexMatch(BotMatcher):
    def __init__(self, regex_pattern: str, regex_flags: Any=0) -> None:
        super().__init__()
        self.pattern = regex_pattern
        self.flag = regex_flags

    def match(self, text: str) -> bool:
        return len(re.findall(self.pattern, text, self.flag)) > 0
