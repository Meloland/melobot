from ..adapter.model import Event
from ..ctx import SessionCtx as _SessionCtx
from .base import SessionStore, enter_session, suspend
from .option import Rule


def get_session_store() -> SessionStore:
    return _SessionCtx().get().store


def get_rule() -> Rule | None:
    return _SessionCtx().get().rule
