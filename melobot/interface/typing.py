from typing import (
    Union, 
    List, 
    Dict, 
    Literal, 
    Coroutine, 
    Callable,
    Tuple,
    Any,
    OrderedDict,
    Optional,
    TypedDict,
    AsyncIterator
)
from enum import Enum
from types import ModuleType


__all__ = (
    'Union', 
    'List', 
    'Dict', 
    'Literal', 
    'Coroutine', 
    'Callable',
    'Tuple',
    'Any',
    'OrderedDict',
    'Optional',
    'ModuleType',
    'AsyncIterator',

    'Enum',
    'Msg',
    'MsgSegment',
    'MsgNode',
    'MsgNodeList',
    'UserLevel',
    'PriorityLevel'
)


class Msg(TypedDict):
    """消息"""
    type: str
    data: Dict[str, Union[int, str]]


# 消息段
MsgSegment = List[Msg]


class CustomMsgNodeData(TypedDict):
    """自定义消息节点数据"""
    name: str
    uin: str
    content: MsgSegment

class ReferMsgNodeData(TypedDict):
    """引用消息节点数据"""
    id: str

class MsgNode(TypedDict):
    """消息节点"""
    type: Literal['node']
    data: Union[CustomMsgNodeData, ReferMsgNodeData]


# 消息节点列表
MsgNodeList = List[MsgNode]


class UserLevel(Enum):
    """权限等级 enum"""
    OWNER = 100
    SU = 90
    WHITE = 80
    USER = 70
    BLACK = -1


class PriorityLevel(Enum):
    """优先级枚举。方便进行优先级比较，有 MIN, MAX, MEAN 三个枚举值"""
    MIN = 0
    MAX = 100
    MEAN = (MAX-MIN)//2