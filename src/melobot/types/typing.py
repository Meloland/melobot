import sys
from enum import Enum
from types import ModuleType
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Callable,
    Coroutine,
    Literal,
    NamedTuple,
    Optional,
    OrderedDict,
    ParamSpec,
    Type,
    TypeAlias,
    TypedDict,
    TypeVar,
    Union,
    cast,
)

import better_exceptions
from typing_extensions import NotRequired

# 修复在 windows powershell 显示错误的 bug
better_exceptions.encoding.ENCODING = sys.stdout.encoding
better_exceptions.formatter.ENCODING = sys.stdout.encoding
better_exceptions.hook()


class CQMsgDict(TypedDict):
    """
    cq 消息 dict
    """

    type: str
    data: dict[str, float | int | str]


class CustomNodeData(TypedDict):
    """
    自定义消息节点 data dict
    """

    name: str
    uin: str
    content: list[CQMsgDict]
    seq: NotRequired[list[CQMsgDict]]


class ReferNodeData(TypedDict):
    """
    引用消息节点 data dict
    """

    id: str


class MsgNodeDict(TypedDict):
    """
    消息节点 dict
    """

    type: Literal["node"]
    data: CustomNodeData | ReferNodeData


class ParseArgs:
    """
    命令参数类
    """

    def __init__(self, values: list[Any] | None) -> None:
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


T = TypeVar("T")
T1 = TypeVar("T1")
T2 = TypeVar("T2")
T3 = TypeVar("T3")
P = ParamSpec("P")


class Void:
    """
    表示无值，而不是 None 代表的“空值”
    """

    pass

VoidType: TypeAlias = Type[Void]
