from .._ctx import FlowCtx as _FlowCtx
from .._di import Depends, inject_deps
from .process import (
    Flow,
    FlowNode,
    PreFlow,
    block,
    bypass,
    flow_to,
    nextp,
    over,
    quit,
    rewind,
)


def get_flow_stack() -> tuple[str, ...]:
    return tuple(_FlowCtx().get().stack)
