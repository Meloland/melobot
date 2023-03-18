from typing import (
    Union, 
    NewType, 
    List, 
    Dict, 
    Literal, 
    Coroutine, 
    Callable,
    TypedDict,
    Tuple,
    Any,
    OrderedDict 
)


__all__ = [
    'Union', 
    'List', 
    'Dict', 
    'Literal', 
    'Coroutine', 
    'Callable',
    'Tuple',
    'Any',
    'NewType',
    'OrderedDict',

    'Msg',
    'MsgSegment',
    'MsgNode',
    'MsgNodeList',
    'UserLevel'
]


MsgData = Dict[str, Union[int, str]]
class Msg(TypedDict):
    """消息"""
    type: str
    data: MsgData


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


# 用户权限等级
UserLevel = NewType('UserLevel', int)