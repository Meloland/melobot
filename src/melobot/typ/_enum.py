from enum import Enum
from logging import CRITICAL, DEBUG, ERROR, INFO, WARNING

from typing_extensions import Any, Callable, assert_never


class ExitCode(Enum):
    NORMAL = 0
    ERROR = 1
    RESTART = 2


# TODO: 考虑在最低支持 3.11 后，使用 logging.getLevelNamesMapping 兼容部分场景
class LogLevel(int, Enum):
    """日志等级枚举"""

    CRITICAL = CRITICAL
    ERROR = ERROR
    WARNING = WARNING
    INFO = INFO
    DEBUG = DEBUG


class LogicMode(Enum):
    """逻辑模式枚举类型"""

    AND = "and"
    OR = "or"
    NOT = "not"
    XOR = "xor"

    def get_operator(self) -> Callable[[Any, Any], bool]:
        match self:
            case LogicMode.AND:
                return lambda x, y: x and y
            case LogicMode.OR:
                return lambda x, y: x or y
            case LogicMode.NOT:
                return lambda x, _: not x
            case LogicMode.XOR:
                return lambda x, y: x ^ y
            case _:
                assert_never(f"不正确的逻辑类型 {self}")
