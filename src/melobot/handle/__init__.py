from ..adapter.model import Event
from ..ctx import FlowCtx as _FlowCtx
from ..ctx import FlowRecord as _FlowRecord
from ..ctx import FlowRecordStage, FlowStore
from .process import Flow, block, bypass, flow_to, nextn, no_deps_node, node, rewind, stop


def get_flow_records() -> tuple[_FlowRecord, ...]:
    return tuple(_FlowCtx().get().records)


def get_flow_store() -> FlowStore:
    return _FlowCtx().get_store()


def get_event() -> Event:
    return _FlowCtx().get_event()


def try_get_event() -> Event | None:
    return _FlowCtx().try_get_event()
