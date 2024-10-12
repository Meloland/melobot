from ..ctx import BotCtx as _BotCtx
from .base import MELO_LAST_EXIT_SIGNAL, MELO_PKG_RUNTIME, Bot, BotExitSignal, BotLifeSpan


def get_bot() -> Bot:
    """获得当前上下文中的 bot 对象

    :return: bot 对象
    """
    return _BotCtx().get()
