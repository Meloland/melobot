from abc import ABC, abstractmethod
from logging import Logger, CRITICAL, DEBUG, ERROR, INFO, WARN, WARNING

from ..models.event import BotEvent, MsgEvent
from .typing import *


class BotChecker(ABC):
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    def check(self, event: BotEvent) -> bool:
        pass


class BotMatcher(ABC):
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    def match(self, event: MsgEvent) -> bool:
        pass


class BotParser(ABC):
    """
    解析器基类。解析器一般用作从消息文本中按规则提取指定字符串或字符串组合
    """
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    def parse(self, event: MsgEvent) -> Union[List[ParseArgs], None]:
        pass
