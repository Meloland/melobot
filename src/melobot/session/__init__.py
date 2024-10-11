from ..ctx import SessionCtx as _SessionCtx
from .base import Session, SessionStore, enter_session, suspend
from .option import Rule


def get_session_store() -> SessionStore:
    """获取当前上下文中的会话存储

    :return: 会话存储
    """
    return _SessionCtx().get().store


def get_rule() -> Rule | None:
    """获取当前上下文中的会话规则

    :return: 会话规则或空
    """
    return _SessionCtx().get().rule
