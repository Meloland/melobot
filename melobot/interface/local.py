from contextvars import ContextVar, Token

from ..interface.plugins import (ExecutorWrapper, IEventExecutor, IBotPlugin,
                                 BotPluginType)
from ..interface.typing import *
from ..interface.utils import BotChecker, BotMatcher, BotParser
from ..models.session import BotSession, SessionRule

_session_ctx = ContextVar("session_ctx")
_plugin_ctx = ContextVar("plugin_ctx")


class SessionLocal:
    """
    session 自动上下文
    """
    __slots__ = tuple(
        list(
            filter(lambda x: not (len(x) >= 2 and x[:2] == '__'), dir(BotSession))
        ) + ['__storage__']
    )

    def __init__(self) -> None:
        object.__setattr__(self, '__storage__', _session_ctx)
        self.__storage__: ContextVar[BotSession]

    def __setattr__(self, __name: str, __value: Any) -> None:
        setattr(self.__storage__.get(), __name, __value)

    def __getattr__(self, __name: str) -> Any:
        return getattr(self.__storage__.get(), __name)
    
    def _add_ctx(self, ctx: BotSession) -> Token:
        return self.__storage__.set(ctx)
    
    def _del_ctx(self, token: Token) -> None:
        self.__storage__.reset(token)


class PluginLocal:
    """
    插件自动上下文对象
    """
    __slots__ = tuple(
        list(
            filter(lambda x: not (len(x) >= 2 and x[:2] == '__'), dir(IBotPlugin))
        ) + ['__storage__']
    )

    def __init__(self) -> None:
        object.__setattr__(self, '__storage__', _plugin_ctx)
        self.__storage__: ContextVar[IBotPlugin]

    def __setattr__(self, __name: str, __value: Any) -> None:
        setattr(self.__storage__.get(), __name, __value)

    def __getattr__(self, __name: str) -> Any:
        return getattr(self.__storage__.get(), __name)
    
    def _add_ctx(self, ctx: IBotPlugin) -> Token:
        return self.__storage__.set(ctx)
    
    def _del_ctx(self, token: Token) -> None:
        self.__storage__.reset(token)

    def at_message(self, matcher: BotMatcher=None, parser: BotParser=None, checker: BotChecker=None, priority: int=PriorityLevel.MEAN, 
                   timeout: int=None, set_block: bool=False, temp: bool=False, session_rule: SessionRule=None, 
                   conflict_wait: bool=False, conflict_callback: Callable[[None], Coroutine]=None, 
                   overtime_callback: Callable[[None], Coroutine]=None
                   ) -> Callable[[IEventExecutor], "ExecutorWrapper"]:
        
        def make_wrapper(executor: IEventExecutor) -> ExecutorWrapper:
            return ExecutorWrapper(
                'at_message',
                executor, 
                [matcher, parser, checker, priority, timeout, set_block, temp, session_rule,
                 conflict_wait, conflict_callback, overtime_callback
                 ]
            )
        return make_wrapper


SESSION_LOCAL: BotSession = SessionLocal()
PLUGIN_LOCAL: BotPluginType = PluginLocal()