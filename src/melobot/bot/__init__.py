from ..ctx import BotCtx as _BotCtx
from .base import MELO_LAST_EXIT_SIGNAL, MELO_PKG_RUNTIME, Bot, BotExitSignal, BotLifeSpan


def get_bot() -> Bot:
    return _BotCtx().get()
