import re

from ..interface.typing import *
from ..interface.utils import BotMatcher
from ..models.event import MsgEvent

__all__ = (
    'BotMatcher',
    'StartMatcher',
    'ContainMatcher',
    'EndMatcher',
    'RegexMatcher'
)


class StartMatcher(BotMatcher):
    def __init__(self, target: str) -> None:
        super().__init__()
        self.target = target

    def match(self, event: MsgEvent) -> bool:
        return event.text[:len(self.target)] == self.target


class ContainMatcher(BotMatcher):
    def __init__(self, target: str, freq: int=1) -> None:
        super().__init__()
        self.target = target
        self.freq = freq

    def match(self, event: MsgEvent) -> bool:
        if self.freq == 1:
            return self.target in event.text
        else:
            return len(re.findall(self.target, event.text)) == self.freq


class EndMatcher(BotMatcher):
    def __init__(self, target: str) -> None:
        super().__init__()
        self.target = target

    def match(self, event: MsgEvent) -> bool:
        return event.text[-len(self.target):-1] == self.target


class FullMatcher(BotMatcher):
    def __init__(self, target: str) -> None:
        super().__init__()
        self.target = target

    def match(self, event: MsgEvent) -> bool:
        return event.text == self.target


class RegexMatcher(BotMatcher):
    def __init__(self, regex_pattern: str, regex_flags: Any=0) -> None:
        super().__init__()
        self.pattern = regex_pattern
        self.flag = regex_flags

    def match(self, event: MsgEvent) -> bool:
        return len(re.findall(self.pattern, event.text, self.flag)) > 0
