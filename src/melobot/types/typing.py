import sys
from enum import Enum
from types import ModuleType
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Callable,
    Coroutine,
    Dict,
    List,
    Literal,
    NamedTuple,
    Optional,
    OrderedDict,
    Set,
    Tuple,
    Type,
    TypeAlias,
    TypedDict,
    TypeVar,
    Union,
)

import better_exceptions

# 修复在 windows powershell 显示错误的 bug
better_exceptions.encoding.ENCODING = sys.stdout.encoding
better_exceptions.formatter.ENCODING = sys.stdout.encoding
better_exceptions.hook()


class CQMsgDict(TypedDict):
    """
    cq 消息 dict
    """

    type: str
    data: Dict[str, float | int | str]


class MsgNodeDict(TypedDict):
    """
    消息节点 dict
    """

    class CustomNodeData(TypedDict):
        """
        自定义消息节点 data dict
        """

        name: str
        uin: int
        content: List[CQMsgDict]

    class ReferNodeData(TypedDict):
        """
        引用消息节点 data dict
        """

        id: int

    type: Literal["node"]
    data: CustomNodeData | ReferNodeData


class ParseArgs:
    """
    命令参数类
    """

    def __init__(self, values: List[Any]) -> None:
        self.vals = values
        self.formatted = False


class User(int, Enum):
    """
    用户权限等级枚举
    """

    OWNER = 10000
    SU = 1000
    WHITE = 100
    USER = 10
    BLACK = -1


class PriorLevel(int, Enum):
    """
    优先级枚举。方便进行优先级比较，有 MIN, MAX, MEAN 三个枚举值
    """

    MIN = 0
    MAX = 1000
    MEAN = (MAX + MIN) // 2


class BotLife(Enum):
    """
    bot 生命周期枚举
    """

    LOADED = 1
    CONNECTED = 2
    BEFORE_CLOSE = 3
    BEFORE_STOP = 4
    EVENT_BUILT = 5
    ACTION_PRESEND = 6


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
            return (v1 and v2) if v2 is not None else bool(v1)
        elif logic == LogicMode.OR:
            return (v1 or v2) if v2 is not None else bool(v1)
        elif logic == LogicMode.NOT:
            return not v1
        elif logic == LogicMode.XOR:
            return (v1 ^ v2) if v2 is not None else bool(v1)

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


T = TypeVar("T")


class Void:
    """
    表示无值，而不是 None 代表的“空值”
    """

    pass
