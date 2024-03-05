from enum import Enum
from types import ModuleType
from typing import (
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
    TypedDict,
    TypeVar,
    Union,
)

__all__ = (
    "Union",
    "List",
    "Set",
    "Dict",
    "Literal",
    "Coroutine",
    "Callable",
    "Tuple",
    "Any",
    "OrderedDict",
    "Optional",
    "ModuleType",
    "AsyncIterator",
    "NamedTuple",
    "AsyncFunc",
    "Type",
    "Enum",
    "CQMsgDict",
    "MsgNodeDict",
    "User",
    "PriorLevel",
    "ParseArgs",
    "Void",
    "T",
)


class CQMsgDict(TypedDict):
    """
    cq 消息 dict
    """

    type: str
    data: Dict[str, Union[float, int, str]]


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
    data: Union[CustomNodeData, ReferNodeData]


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

    OWNER = 100
    SU = 90
    WHITE = 80
    USER = 70
    BLACK = -1


class PriorLevel(int, Enum):
    """
    优先级枚举。方便进行优先级比较，有 MIN, MAX, MEAN 三个枚举值
    """

    MIN = -100
    MAX = 100
    MEAN = (MAX + MIN) // 2


T = TypeVar("T")
AsyncFunc = Callable[..., Coroutine[Any, Any, T]]


class Void:
    """
    表示无值，而不是 None 代表的“空值”
    """

    pass
