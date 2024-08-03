from contextvars import ContextVar, Token

from ..exceptions import BotRuntimeError
from ..plugin.ipc import IPCManager
from ..typing import Any, cast
from ..utils import singleton


class Bot:
    def __init__(self) -> None:
        self.ipc_manager = IPCManager()


@singleton
class BotLocal:
    """bot 实例自动上下文"""

    def __init__(self) -> None:
        object.__setattr__(self, "__storage__", ContextVar("bot_ctx"))
        self.__storage__: ContextVar["Bot"]

    def get(self) -> Bot:
        try:
            return self.__storage__.get()
        except LookupError:
            raise BotRuntimeError("bot 实例尚未建立，此时无法获取 bot 实例")

    def add(self, ctx: Bot) -> Token:
        return self.__storage__.set(ctx)

    def remove(self, token: Token) -> None:
        self.__storage__.reset(token)


def get_bot() -> Bot:
    return BotLocal().get()
