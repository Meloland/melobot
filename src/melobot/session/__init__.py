from .._ctx import SessionCtx as _SessionCtx
from ..adapter.model import Event
from .base import StoreT, suspend
from .option import Rule, SessionOption


def get_event() -> Event:
    return _SessionCtx().get_event()


def get_store() -> StoreT:
    return _SessionCtx().get().store


def get_rule() -> Rule | None:
    return _SessionCtx().get().rule
