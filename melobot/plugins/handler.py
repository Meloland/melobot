import asyncio as aio

from ..interface.core import IActionResponder
from ..interface.local import PLUGIN_LOCAL, SESSION_LOCAL
from ..models.session import SessionRule
from ..interface.plugins import IEventExecutor, IEventHandler, IBotPlugin
from ..interface.typing import *
from ..interface.utils import BotChecker, BotMatcher, BotParser, ParserParams
from ..models.event import BotEvent, MsgEvent, NoticeEvent, RequestEvent
from ..models.exceptions import *
from ..models.session import BotSession, BotSessionManager


class MsgEventHandler(IEventHandler):
    def __init__(self, executor: IEventExecutor, plugin_ref: IBotPlugin, responder: IActionResponder, matcher: BotMatcher=None, 
                 parser: BotParser=None, checker: BotChecker=None, priority: int=PriorityLevel.MEAN.value, timeout: float=None, 
                 set_block: bool=False, temp: bool=False, session_rule: SessionRule=None, conflict_wait: bool=False, 
                 conflict_callback: Callable[[None], Coroutine]=None, overtime_callback: Callable[[None], Coroutine]=None
                 ) -> None:
        """
        matcher_wrapper 和 parser 必须一个为 None, 另一存在。
        """
        super().__init__(priority, timeout, set_block, temp)

        self.executor = executor
        self.responder = responder
        self.matcher = matcher
        self.parser = parser
        self.checker = checker
        self.exec_lock = aio.Lock()

        self._session_rule = session_rule
        self._plugin_ref = plugin_ref
        self._conflict_cb = conflict_callback
        self._overtime_cb = overtime_callback
        self._wait = conflict_wait
        self._session_space = []
        self._session_lock = aio.Lock()

        if (self.matcher is None and self.parser is None) or \
            (self.matcher and self.parser):
            raise BotValueError("matcher 和 parser 不能同时为空或同时存在")

    def verify(self, event: MsgEvent) -> bool:
        """
        验证处理事件的前置条件
        """
        if self.checker:
            if self.checker.check(event):
                pass
            else:
                return False

        if self.matcher:
            return self.matcher.match(event)
        if self.parser:
            args = self.parser.parse(event)
            event._set_args(args)
            return args is not None
        
    async def _run_with_ctx(self, coro: Coroutine, session: BotSession=None, plugin_ref: IBotPlugin=None, timeout: float=None) -> None:
        """
        在指定上下文下运行。异常将会抛出
        """
        try:
            s_token = SESSION_LOCAL._add_ctx(session)
            p_token = PLUGIN_LOCAL._add_ctx(plugin_ref)
            await aio.wait_for(aio.create_task(coro), timeout=timeout)
        finally:
            PLUGIN_LOCAL._del_ctx(p_token)
            SESSION_LOCAL._del_ctx(s_token)

    async def _handle(self, session: BotSession) -> None:
        """
        正式开始运行 executor
        """
        exec_coro: Coroutine = self.executor()
        try:
            await self._run_with_ctx(exec_coro, session, self._plugin_ref, self.timeout)
        except aio.TimeoutError:
            if self._overtime_cb:
                await self._run_with_ctx(self._overtime_cb(), session, self._plugin_ref)

    async def handle(self, event: MsgEvent) -> None:
        session = await BotSessionManager.get(event, self.responder, self._session_lock, self._session_rule, 
                                              self._session_space, self._wait)
        if session is None: 
            if self._conflict_cb:
                temp_session = await BotSessionManager.get(event, self.responder)
                await self._run_with_ctx(self._conflict_cb(), temp_session, plugin_ref=self._plugin_ref)
            return
        
        await self._handle(session)
        BotSessionManager.recycle(session)


class ReqEventHandler(IEventHandler):
    def __init__(self, executor: IEventExecutor, plugin_ref: IBotPlugin, responder: IActionResponder, checker: BotChecker=None, 
                 priority: int=PriorityLevel.MEAN.value, timeout: float=None, set_block: bool=False, temp: bool=False, 
                 session_rule: SessionRule=None, conflict_wait: bool=False, conflict_callback: Callable[[None], Coroutine]=None, 
                 overtime_callback: Callable[[None], Coroutine]=None
                 ) -> None:
        super().__init__(priority, timeout, set_block, temp)

        self.executor = executor
        self.responder = responder
        self.checker = checker
        self.exec_lock = aio.Lock()

        self._session_rule = session_rule
        self._plugin_ref = plugin_ref
        self._conflict_cb = conflict_callback
        self._overtime_cb = overtime_callback
        self._wait = conflict_wait
        self._session_space = []
        self._session_lock = aio.Lock()

    def verify(self, event: BotEvent) -> bool:
        if self.checker:
            return self.checker.check(event)
        else:
            return True
        
    async def _run_with_ctx(self, coro: Coroutine, session: BotSession=None, plugin_ref: IBotPlugin=None, timeout: float=None) -> None:
        """
        在指定上下文下运行。异常将会抛出
        """
        try:
            s_token = SESSION_LOCAL._add_ctx(session)
            p_token = PLUGIN_LOCAL._add_ctx(plugin_ref)
            await aio.wait_for(aio.create_task(coro), timeout=timeout)
        finally:
            PLUGIN_LOCAL._del_ctx(p_token)
            SESSION_LOCAL._del_ctx(s_token)

    async def _handle(self, session: BotSession) -> None:
        """
        正式开始运行 executor
        """
        exec_coro: Coroutine = self.executor()
        try:
            await self._run_with_ctx(exec_coro, session, self._plugin_ref, self.timeout)
        except aio.TimeoutError:
            if self._overtime_cb:
                await self._run_with_ctx(self._overtime_cb(), session, self._plugin_ref)

    async def handle(self, event: RequestEvent) -> None:
        session = await BotSessionManager.get(event, self.responder, self._session_lock, self._session_rule, 
                                              self._session_space, self._wait)
        if session is None: 
            if self._conflict_cb:
                temp_session = await BotSessionManager.get(event, self.responder)
                await self._run_with_ctx(self._conflict_cb(), temp_session, plugin_ref=self._plugin_ref)
            return
        
        await self._handle(session)
        BotSessionManager.recycle(session)


class NoticeEventHandler(IEventHandler):
    def __init__(self, executor: IEventExecutor, plugin_ref: IBotPlugin, responder: IActionResponder, checker: BotChecker=None, 
                 priority: int=PriorityLevel.MEAN.value, timeout: float=None, set_block: bool=False, temp: bool=False, 
                 session_rule: SessionRule=None, conflict_wait: bool=False, conflict_callback: Callable[[None], Coroutine]=None, 
                 overtime_callback: Callable[[None], Coroutine]=None
                 ) -> None:
        super().__init__(priority, timeout, set_block, temp)

        self.executor = executor
        self.responder = responder
        self.checker = checker
        self.exec_lock = aio.Lock()

        self._session_rule = session_rule
        self._plugin_ref = plugin_ref
        self._conflict_cb = conflict_callback
        self._overtime_cb = overtime_callback
        self._wait = conflict_wait
        self._session_space = []
        self._session_lock = aio.Lock()

    def verify(self, event: BotEvent) -> bool:
        if self.checker:
            return self.checker.check(event)
        else:
            return True
        
    async def _run_with_ctx(self, coro: Coroutine, session: BotSession=None, plugin_ref: IBotPlugin=None, timeout: float=None) -> None:
        """
        在指定上下文下运行。异常将会抛出
        """
        try:
            s_token = SESSION_LOCAL._add_ctx(session)
            p_token = PLUGIN_LOCAL._add_ctx(plugin_ref)
            await aio.wait_for(aio.create_task(coro), timeout=timeout)
        finally:
            PLUGIN_LOCAL._del_ctx(p_token)
            SESSION_LOCAL._del_ctx(s_token)

    async def _handle(self, session: BotSession) -> None:
        """
        正式开始运行 executor
        """
        exec_coro: Coroutine = self.executor()
        try:
            await self._run_with_ctx(exec_coro, session, self._plugin_ref, self.timeout)
        except aio.TimeoutError:
            if self._overtime_cb:
                await self._run_with_ctx(self._overtime_cb(), session, self._plugin_ref)

    async def handle(self, event: NoticeEvent) -> None:
        session = await BotSessionManager.get(event, self.responder, self._session_lock, self._session_rule, 
                                              self._session_space, self._wait)
        if session is None: 
            if self._conflict_cb:
                temp_session = await BotSessionManager.get(event, self.responder)
                await self._run_with_ctx(self._conflict_cb(), temp_session, plugin_ref=self._plugin_ref)
            return
        
        await self._handle(session)
        BotSessionManager.recycle(session)