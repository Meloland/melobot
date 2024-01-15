from abc import ABC, abstractmethod
from logging import CRITICAL, DEBUG, ERROR, INFO, WARN, WARNING, Logger

from ..models.event import BotEvent
from .typing import *


class LogicMode(Enum):
    """
    逻辑模式枚举
    """
    AND = 1
    OR = 2
    NOT = 3
    XOR = 4


class BotChecker(ABC):
    def __init__(self) -> None:
        super().__init__()

    def __and__(self, other: "BotChecker") -> "WrappedChecker":
        return WrappedChecker(LogicMode.AND, self, other)
    
    def __or__(self, other: "BotChecker") -> "WrappedChecker":
        return WrappedChecker(LogicMode.OR, self, other)
    
    def __invert__(self) -> "WrappedMatcher":
        return WrappedChecker(LogicMode.NOT, self)
    
    def __xor__(self, other: "BotChecker") -> "WrappedChecker":
        return WrappedChecker(LogicMode.XOR, self, other)

    @abstractmethod
    def check(self, event: BotEvent) -> bool:
        pass


class WrappedChecker(BotChecker):
    """
    按逻辑关系工作的的合并检查器，使用 AND 和 OR 模式时，
    需要传递两个 checker。使用 NOT 时只需要传递第一个 checker
    """
    def __init__(self, mode: LogicMode, checker1: BotChecker, checker2: BotChecker=None) -> None:
        super().__init__()
        self.mode = mode
        self.c1, self.c2 = checker1, checker2

    def check(self, event: BotEvent) -> bool:
        if self.mode == LogicMode.AND:
            return self.c1.check(event) and self.c2.check(event)
        elif self.mode == LogicMode.OR:
            return self.c1.check(event) or self.c2.check(event)
        elif self.mode == LogicMode.NOT:
            return not self.c1.check(event)
        elif self.mode == LogicMode.XOR:
            return self.c1.check(event) ^ self.c2.check(event)


class BotMatcher(ABC):
    def __init__(self) -> None:
        super().__init__()

    def __and__(self, other: "BotMatcher") -> "WrappedMatcher":
        return WrappedMatcher(LogicMode.AND, self, other)
    
    def __or__(self, other: "BotMatcher") -> "WrappedMatcher":
        return WrappedMatcher(LogicMode.OR, self, other)
    
    def __invert__(self) -> "WrappedMatcher":
        return WrappedMatcher(LogicMode.NOT, self)
    
    def __xor__(self, other: "BotMatcher") -> "WrappedMatcher":
        return WrappedMatcher(LogicMode.XOR, self, other)

    @abstractmethod
    def match(self, text: str) -> bool:
        pass


class WrappedMatcher(BotMatcher):
    """
    按逻辑关系工作的的合并匹配器，使用 AND 和 OR 模式时，
    需要传递两个 matcher。使用 NOT 时只需要传递第一个 matcher
    """
    def __init__(self, mode: LogicMode, matcher1: BotMatcher, matcher2: BotMatcher=None) -> None:
        super().__init__()
        self.mode = mode
        self.m1, self.m2 = matcher1, matcher2

    def match(self, text: str) -> bool:
        if self.mode == LogicMode.AND:
            return self.m1.match(text) and self.m2.match(text)
        elif self.mode == LogicMode.OR:
            return self.m1.match(text) or self.m2.match(text)
        elif self.mode == LogicMode.NOT:
            return not self.m1.match(text)
        elif self.mode == LogicMode.XOR:
            return self.m1.match(text) ^ self.m2.match(text)


class BotParser(ABC):
    """
    解析器基类。解析器一般用作从消息文本中按规则提取指定字符串或字符串组合
    """
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    def parse(self, text: str) -> Union[List[ParseArgs], None]:
        pass
