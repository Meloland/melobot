from .._ctx import FlowCtx as _FlowCtx
from .._ctx import FlowRecord as _FlowRecord
from .._ctx import FlowRecordStage, FlowStore
from .._di import Depends, inject_deps
from ..adapter.model import Event
from .process import Flow, block, bypass, flow_to, nextn, node, rewind, stop


def get_flow_records() -> tuple[_FlowRecord, ...]:
    return tuple(_FlowCtx().get().records)


def get_flow_store() -> FlowStore:
    return _FlowCtx().get_store()


def get_event() -> Event:
    return _FlowCtx().get_event()


def try_get_event() -> Event | None:
    return _FlowCtx().try_get_event()
