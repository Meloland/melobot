from abc import ABC, abstractmethod
from collections.abc import Mapping
from logging import CRITICAL, DEBUG, ERROR, INFO, WARN, WARNING, Logger
from types import TracebackType
from typing import TypeAlias

from ..models.event import BotEvent
from .typing import *


_SysExcInfoType: TypeAlias = Union[
    tuple[type[BaseException], BaseException, Optional[TracebackType]],
    tuple[None, None, None],
]
_ExcInfoType: TypeAlias = Union[None, bool, _SysExcInfoType, BaseException]


class WrappedLogger:
    """
    二次包装的日志器
    """
    def __init__(self, ref: Logger, prefix: str) -> None:
        self._logger = ref
        self._prefix = prefix

    def _add_prefix(self, s: str) -> str:
        return f"[{self._prefix}] {s}"

    def info(self, msg: object, *args: object, exc_info: _ExcInfoType = None, stack_info: bool = False, 
             stacklevel: int = 1, extra: Mapping[str, object] | None = None) -> None:
        msg = self._add_prefix(msg)
        return self._logger.info(msg, *args, exc_info=exc_info, stack_info=stack_info, stacklevel=stacklevel, extra=extra)
    
    def warn(self, msg: object, *args: object, exc_info: _ExcInfoType = None, stack_info: bool = False, 
             stacklevel: int = 1, extra: Mapping[str, object] | None = None) -> None:
        msg = self._add_prefix(msg)
        return self._logger.warn(msg, *args, exc_info=exc_info, stack_info=stack_info, stacklevel=stacklevel, extra=extra)
    
    def warning(self, msg: object, *args: object, exc_info: _ExcInfoType = None, stack_info: bool = False, 
                stacklevel: int = 1, extra: Mapping[str, object] | None = None) -> None:
        msg = self._add_prefix(msg)
        return self._logger.warning(msg, *args, exc_info=exc_info, stack_info=stack_info, stacklevel=stacklevel, extra=extra)
    
    def error(self, msg: object, *args: object, exc_info: _ExcInfoType = None, stack_info: bool = False, 
              stacklevel: int = 1, extra: Mapping[str, object] | None = None) -> None:
        msg = self._add_prefix(msg)
        return self._logger.error(msg, *args, exc_info=exc_info, stack_info=stack_info, stacklevel=stacklevel, extra=extra)
    
    def debug(self, msg: object, *args: object, exc_info: _ExcInfoType = None, stack_info: bool = False, 
              stacklevel: int = 1, extra: Mapping[str, object] | None = None) -> None:
        msg = self._add_prefix(msg)
        return self._logger.debug(msg, *args, exc_info=exc_info, stack_info=stack_info, stacklevel=stacklevel, extra=extra)
    
    def critical(self, msg: object, *args: object, exc_info: _ExcInfoType = None, stack_info: bool = False, 
                 stacklevel: int = 1, extra: Mapping[str, object] | None = None) -> None:
        msg = self._add_prefix(msg)
        return self._logger.critical(msg, *args, exc_info=exc_info, stack_info=stack_info, stacklevel=stacklevel, extra=extra)


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
    def __init__(self, id: Any) -> None:
        super().__init__()
        self.id = id
        self.need_format: bool = False

    @abstractmethod
    def parse(self, text: str) -> Union[Dict[str, ParseArgs], None]:
        pass

    @abstractmethod
    def test(self, args_group: Dict[str, ParseArgs]) -> Tuple[bool, Union[str, None], Union[ParseArgs, None]]:
        pass

    @abstractmethod
    def format(self, args: ParseArgs) -> None:
        pass
