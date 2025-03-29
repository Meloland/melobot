from typing_extensions import Any

from ..ctx import SessionCtx as _SessionCtx
from .base import Session, SessionStore, enter_session, suspend
from .option import CompareInfo, DefaultRule, Rule


def get_session() -> Session:
    """获取当前上下文中的会话

    :return: 会话
    """
    return _SessionCtx().get()


def get_session_store() -> SessionStore:
    """获取当前上下文中的会话存储

    :return: 会话存储
    """
    return _SessionCtx().get().store


def get_rule() -> Rule:
    """获取当前上下文中的会话规则

    :return: 会话规则
    """
    return _SessionCtx().get_rule()


def __getattr__(name: str) -> Any:
    if name == "session":
        return get_session()
    elif name == "s_store":
        return get_session_store()
    elif name == "rule":
        return get_rule()
    else:
        raise AttributeError


session: Session
"""当前上下文中的会话"""

s_store: SessionStore
"""当前上下文中的会话存储"""

rule: Rule
"""当前上下文中的会话规则"""
