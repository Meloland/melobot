from abc import ABC, abstractmethod
from collections.abc import Mapping
from logging import Logger
from types import TracebackType
from typing import TypeAlias

from ..models.event import BotEvent
from .exceptions import *
from .typing import *

_SysExcInfoType: TypeAlias = Union[
    Tuple[Type[BaseException], BaseException, Optional[TracebackType]],
    Tuple[None, None, None],
]
_ExcInfoType: TypeAlias = Union[None, bool, _SysExcInfoType, BaseException]


class PrefixLogger:
    """
    二次包装的日志器
    """

    def __init__(self, ref: Logger, prefix: str) -> None:
        self._logger = ref
        self._prefix = prefix

    def _add_prefix(self, s: str) -> str:
        return f"[{self._prefix}] {s}"

    def info(
        self,
        msg: object,
        *args: object,
        exc_info: _ExcInfoType = None,
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Union[Mapping[str, object], None] = None,
    ) -> None:
        msg = self._add_prefix(msg)
        return self._logger.info(
            msg,
            *args,
            exc_info=exc_info,
            stack_info=stack_info,
            stacklevel=stacklevel,
            extra=extra,
        )

    def warn(
        self,
        msg: object,
        *args: object,
        exc_info: _ExcInfoType = None,
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Union[Mapping[str, object], None] = None,
    ) -> None:
        msg = self._add_prefix(msg)
        return self._logger.warn(
            msg,
            *args,
            exc_info=exc_info,
            stack_info=stack_info,
            stacklevel=stacklevel,
            extra=extra,
        )

    def warning(
        self,
        msg: object,
        *args: object,
        exc_info: _ExcInfoType = None,
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Union[Mapping[str, object], None] = None,
    ) -> None:
        msg = self._add_prefix(msg)
        return self._logger.warning(
            msg,
            *args,
            exc_info=exc_info,
            stack_info=stack_info,
            stacklevel=stacklevel,
            extra=extra,
        )

    def error(
        self,
        msg: object,
        *args: object,
        exc_info: _ExcInfoType = None,
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Union[Mapping[str, object], None] = None,
    ) -> None:
        msg = self._add_prefix(msg)
        return self._logger.error(
            msg,
            *args,
            exc_info=exc_info,
            stack_info=stack_info,
            stacklevel=stacklevel,
            extra=extra,
        )

    def debug(
        self,
        msg: object,
        *args: object,
        exc_info: _ExcInfoType = None,
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Union[Mapping[str, object], None] = None,
    ) -> None:
        msg = self._add_prefix(msg)
        return self._logger.debug(
            msg,
            *args,
            exc_info=exc_info,
            stack_info=stack_info,
            stacklevel=stacklevel,
            extra=extra,
        )

    def critical(
        self,
        msg: object,
        *args: object,
        exc_info: _ExcInfoType = None,
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Union[Mapping[str, object], None] = None,
    ) -> None:
        msg = self._add_prefix(msg)
        return self._logger.critical(
            msg,
            *args,
            exc_info=exc_info,
            stack_info=stack_info,
            stacklevel=stacklevel,
            extra=extra,
        )


class LogicMode(Enum):
    """
    逻辑模式枚举
    """

    AND = 1
    OR = 2
    NOT = 3
    XOR = 4

    @classmethod
    def calc(cls, logic: "LogicMode", v1: Any, v2: Any = None) -> bool:
        if logic == LogicMode.AND:
            return v1 and v2
        elif logic == LogicMode.OR:
            return v1 or v2
        elif logic == LogicMode.NOT:
            return not v1
        elif logic == LogicMode.XOR:
            return v1 ^ v2

    @classmethod
    def seq_calc(cls, logic: "LogicMode", values: List[Any]) -> bool:
        if len(values) <= 0:
            return False
        elif len(values) <= 1:
            return bool(values[0])

        idx = 0
        res = None
        while idx < len(values):
            if idx == 0:
                res = cls.calc(logic, values[idx], values[idx + 1])
                idx += 1
            else:
                res = cls.calc(logic, res, values[idx])
            idx += 1
        return res


class BotChecker(ABC):
    def __init__(self) -> None:
        super().__init__()

    def __and__(self, other: "BotChecker") -> "WrappedChecker":
        if not isinstance(other, BotChecker):
            raise BotCheckerError(
                f"联合检查器定义时出现了非检查器对象，其值为：{other}"
            )
        return WrappedChecker(LogicMode.AND, self, other)

    def __or__(self, other: "BotChecker") -> "WrappedChecker":
        if not isinstance(other, BotChecker):
            raise BotCheckerError(
                f"联合检查器定义时出现了非检查器对象，其值为：{other}"
            )
        return WrappedChecker(LogicMode.OR, self, other)

    def __invert__(self) -> "WrappedMatcher":
        return WrappedChecker(LogicMode.NOT, self)

    def __xor__(self, other: "BotChecker") -> "WrappedChecker":
        if not isinstance(other, BotChecker):
            raise BotCheckerError(
                f"联合检查器定义时出现了非检查器对象，其值为：{other}"
            )
        return WrappedChecker(LogicMode.XOR, self, other)

    @abstractmethod
    def check(self, event: BotEvent) -> bool:
        pass


class WrappedChecker(BotChecker):
    """
    按逻辑关系工作的的合并检查器，使用 AND, OR, XOR 模式时，
    需要传递两个 checker。使用 NOT 时只需要传递第一个 checker
    """

    def __init__(
        self, mode: LogicMode, checker1: BotChecker, checker2: BotChecker = None
    ) -> None:
        super().__init__()
        self.mode = mode
        self.c1, self.c2 = checker1, checker2

    def check(self, event: BotEvent) -> bool:
        return LogicMode.calc(
            self.mode,
            self.c1.check(event),
            self.c2.check(event) if self.c2 is not None else None,
        )


class BotMatcher(ABC):
    def __init__(self) -> None:
        super().__init__()

    def __and__(self, other: "BotMatcher") -> "WrappedMatcher":
        if not isinstance(other, BotMatcher):
            raise BotMatcherError(
                f"联合匹配器定义时出现了非匹配器对象，其值为：{other}"
            )
        return WrappedMatcher(LogicMode.AND, self, other)

    def __or__(self, other: "BotMatcher") -> "WrappedMatcher":
        if not isinstance(other, BotMatcher):
            raise BotMatcherError(
                f"联合匹配器定义时出现了非匹配器对象，其值为：{other}"
            )
        return WrappedMatcher(LogicMode.OR, self, other)

    def __invert__(self) -> "WrappedMatcher":
        return WrappedMatcher(LogicMode.NOT, self)

    def __xor__(self, other: "BotMatcher") -> "WrappedMatcher":
        if not isinstance(other, BotMatcher):
            raise BotMatcherError(
                f"联合匹配器定义时出现了非匹配器对象，其值为：{other}"
            )
        return WrappedMatcher(LogicMode.XOR, self, other)

    @abstractmethod
    def match(self, text: str) -> bool:
        pass


class WrappedMatcher(BotMatcher):
    """
    按逻辑关系工作的的合并匹配器，使用 AND, OR, XOR 模式时，
    需要传递两个 matcher。使用 NOT 时只需要传递第一个 matcher
    """

    def __init__(
        self, mode: LogicMode, matcher1: BotMatcher, matcher2: BotMatcher = None
    ) -> None:
        super().__init__()
        self.mode = mode
        self.m1, self.m2 = matcher1, matcher2

    def match(self, text: str) -> bool:
        return LogicMode.calc(
            self.mode,
            self.m1.match(text),
            self.m2.match(text) if self.m2 is not None else None,
        )


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
    def test(
        self, args_group: Dict[str, ParseArgs]
    ) -> Tuple[bool, Union[str, None], Union[ParseArgs, None]]:
        pass

    @abstractmethod
    def format(self, args: ParseArgs) -> None:
        pass
