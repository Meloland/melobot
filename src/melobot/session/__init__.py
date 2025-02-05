from ..ctx import SessionCtx as _SessionCtx
from .base import Session, SessionStore, enter_session, suspend
from .option import DefaultRule, Rule


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
    rule = _SessionCtx().get().rule
    assert rule is not None, "预期之外的会话规则为空"
    return rule
