import asyncio as aio

from ..interface.plugin import IHookCaller, IHookRunner
from ..interface.typing import *
from ..utils.config import BotConfig
from ..utils.store import BotStore
from ..interface.core import IEventDispatcher, IActionSender, IActionResponder
from .plugin import BotPlugin, PLUGIN_LOCAL
from ..models.session import BotSessionManager, SESSION_LOCAL
from ..interface.core import IActionResponder

class BotProxy:
    """
    暴露给外部使用的 BotProxy 代理对象
    """
    def __init__(self) -> None:
        self.store = BotStore()
        
        self.config: BotConfig
        self._work: aio.Task
        self._linker: IActionSender
        self._responder: IActionResponder
        self._dispatcher: IEventDispatcher

    def bind(self, config: BotConfig, work: aio.Task, linker: IActionSender, responder: IActionResponder, dispatcher: IEventDispatcher) -> None:
        self.config = config
        self._work = work
        self._linker = linker
        self._responder = responder
        self._dispatcher = dispatcher
    
    def after_connect(self, caller: IHookCaller) -> Callable:
        return caller, ConnectedHookRunner, []
    
    def at_close(self, caller: IHookCaller) -> Callable:
        return caller, CloseHookRunner, []


BOT_PROXY = BotProxy()


# TODO: 相同的逻辑移到基类中
class ConnectedHookRunner(IHookRunner):
    def __init__(self, caller: IHookCaller, plguin_ref: BotPlugin, responder: IActionResponder) -> None:
        super().__init__()
        self.caller = caller
        
        self._plugin_ref = plguin_ref
        self._responder = responder

    async def run(self) -> None:
        temp_session = BotSessionManager.get(None, self._responder)
        try:
            s_token = SESSION_LOCAL._add_ctx(temp_session)
            p_token = PLUGIN_LOCAL._add_ctx(self._plugin_ref)
            await self.caller()
        finally:
            PLUGIN_LOCAL._del_ctx(p_token)
            SESSION_LOCAL._del_ctx(s_token)


class CloseHookRunner(IHookRunner):
    def __init__(self, caller: IHookCaller, plguin_ref: BotPlugin, responder: IActionResponder) -> None:
        super().__init__()
        self.caller = caller
        
        self._plugin_ref = plguin_ref
        self._responder = responder

    async def run(self) -> None:
        temp_session = BotSessionManager.get(None, self._responder)
        try:
            s_token = SESSION_LOCAL._add_ctx(temp_session)
            p_token = PLUGIN_LOCAL._add_ctx(self._plugin_ref)
            await self.caller()
        finally:
            PLUGIN_LOCAL._del_ctx(p_token)
            SESSION_LOCAL._del_ctx(s_token)
