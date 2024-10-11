from ..adapter.model import Event as _Event
from ..ctx import FlowCtx as _FlowCtx
from ..ctx import FlowRecord, FlowRecordStage, FlowStore
from .process import (
    Flow,
    FlowNode,
    block,
    bypass,
    flow_to,
    nextn,
    no_deps_node,
    node,
    rewind,
    stop,
)


def get_flow_records() -> tuple[FlowRecord, ...]:
    """获取当前上下文中的流记录

    :return: 流记录
    """
    return tuple(_FlowCtx().get().records)


def get_flow_store() -> FlowStore:
    """获取当前上下文中的流存储

    :return: 流存储
    """
    return _FlowCtx().get_store()


def get_event() -> _Event:
    """获取当前上下文中的事件

    :return: 事件
    """
    return _FlowCtx().get_event()


def try_get_event() -> _Event | None:
    """尝试获取当前上下文中的事件

    :return: 事件或空
    """
    return _FlowCtx().try_get_event()
