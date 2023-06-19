from abc import ABC, abstractmethod

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


class ParserParams:
    """
    解析参数类
    """
    def __init__(self, param_list: List[str]) -> None:
        self.values = param_list


class BotParser(ABC):
    """
    解析器基类。解析器一般用作从消息文本中按规则
    提取指定字符串或字符串组合
    """
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    def parse(self, event: MsgEvent) -> Union[List[ParserParams], None]:
        pass