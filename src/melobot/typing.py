from enum import Enum
from types import TracebackType
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Generic,
    Iterator,
    Literal,
    Optional,
    ParamSpec,
    Type,
    TypeAlias,
    TypedDict,
    TypeVar,
    Union,
    cast,
)

# class ParseArgs:
#     """解析参数类"""

#     def __init__(self, values: list[Any]) -> None:
#         """实例化一组解析参数，对应一次解析的结果

#         :param values: 参数值的列表（表示无可用参数用空列表，而不是 None 值）
#         """
#         #: 保存的一组解析参数值
#         self.vals: list[Any] = values


class LogicMode(Enum):
    """逻辑模式枚举类型"""

    AND = 1
    OR = 2
    NOT = 3
    XOR = 4

    @classmethod
    def calc(cls, logic: "LogicMode", v1: Any, v2: Any = None) -> bool:
        if logic == LogicMode.AND:
            return (v1 and v2) if v2 is not None else bool(v1)
        elif logic == LogicMode.OR:
            return (v1 or v2) if v2 is not None else bool(v1)
        elif logic == LogicMode.NOT:
            return not v1
        elif logic == LogicMode.XOR:
            return (v1 ^ v2) if v2 is not None else bool(v1)

    @classmethod
    def seq_calc(cls, logic: "LogicMode", values: list[Any]) -> bool:
        if len(values) <= 0:
            return False
        elif len(values) <= 1:
            return bool(values[0])

        idx = 0
        res: bool
        while idx < len(values):
            if idx == 0:
                res = cls.calc(logic, values[idx], values[idx + 1])
                idx += 1
            else:
                res = cls.calc(logic, res, values[idx])
            idx += 1
        return res


# # TODO: 若无额外依赖，则移动到具体模块中
# class User(int, Enum):
#     """用户权限等级枚举"""

#     OWNER = 10000
#     SU = 1000
#     WHITE = 100
#     USER = 10
#     BLACK = -1


# TODO: 若无额外依赖，则移动到具体模块中
class HandlePriority(int, Enum):
    """事件处理优先级枚举

    为方便进行优先级设置，有 MIN, MAX, MEAN 三个枚举值
    """

    MIN = 0
    MAX = 1000
    MEAN = (MAX + MIN) // 2


class BotLife(Enum):
    """bot 实例的生命周期枚举"""

    LOADED = 1
    FIRST_CONNECTED = 2
    RECONNECTED = 3
    BEFORE_CLOSE = 4
    BEFORE_STOP = 5
    EVENT_BUILT = 6
    ACTION_PRESEND = 7


#: 泛型 T，无约束
T = TypeVar("T")
#: :obj:`typing.ParamSpec` 泛型 P，无约束
P = ParamSpec("P")
#: 参数为 P，返回 Awaitable[T] 的可调用对象
AsyncCallable: TypeAlias = Callable[P, Awaitable[T]]
