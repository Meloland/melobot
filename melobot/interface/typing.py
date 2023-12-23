import os
import sys

from typing import (
    Union, 
    List, 
    Set,
    Dict, 
    Literal, 
    Coroutine, 
    Callable,
    Tuple,
    Any,
    OrderedDict,
    Optional,
    TypedDict,
    AsyncIterator,
    NamedTuple
)
from enum import Enum
from types import ModuleType


__all__ = (
    'Union', 
    'List', 
    'Set',
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
    'NamedTuple',

    'Enum',
    'Msg',
    'MsgSegment',
    'MsgNode',
    'MsgNodeList',
    'UserLevel',
    'PriorityLevel',
    'METAINFO'
)


class Singleton:
    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '__instance__'):
            cls.__instance__ = super(Singleton, cls).__new__(cls)
        return cls.__instance__


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


class UserLevel(int, Enum):
    """权限等级枚举"""
    OWNER = 100
    SU = 90
    WHITE = 80
    USER = 70
    BLACK = -1


class PriorityLevel(int, Enum):
    """优先级枚举。方便进行优先级比较，有 MIN, MAX, MEAN 三个枚举值"""
    MIN = -100
    MAX = 100
    MEAN = (MAX+MIN)//2


class MetaInfo:
    def __init__(self) -> None:
        self.VER = '2.0.0-Beta1'
        self.PROJ_NAME = 'MeloBot'
        self.AUTHOR = 'AiCorein'
        self.PROJ_SRC = 'https://github.com/AiCorein/Qbot-MeloBot'
        self.PLATFORM = sys.platform
        self.OS_SEP = os.sep
        self.PATH_SEP = os.pathsep

METAINFO = MetaInfo()