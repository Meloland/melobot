import asyncio as aio
import importlib.util
import os
from asyncio import iscoroutinefunction
from contextvars import ContextVar, Token

from ..interface.core import IActionResponder
from ..interface.plugin import (IEventExecutor, IEventHandler, IHookCaller,
                                IHookRunner, PluginTemplate)
from ..interface.typing import *
from ..interface.utils import BotChecker, BotMatcher, BotParser
from ..models.event import BotEvent, MsgEvent, NoticeEvent, RequestEvent
from ..models.exceptions import *
from ..models.session import (SESSION_LOCAL, BotSession, BotSessionManager,
                              SessionRule)


class BotPlugin:
    """
    bot 插件类。
    bot 所有自定义功能都由插件实现。
    """
    __public_attrs__ = ('name', 'version', 'rw_auth', 'call_auth')

    def __init__(self, dir: str, template: PluginTemplate, responder: IActionResponder) -> None:
        self._template = template
        self._responder = responder
        
        self.name: str=None
        self.dir: str=dir
        self.version: str=None
        self.rw_auth: bool=False
        self.call_auth: bool=False
        self.store: Dict[str, Any]={}

        self.handlers: List[IEventHandler]=None
        self.runners: List[IHookRunner]=None

        self._build()

    def _build(self) -> None:
        """
        从模板初始化插件
        """
        executor_wrappers = None
        caller_wrappers = None

        for name in self._template.__dict__.keys():
            if name == 'executors':
                executor_wrappers = self._template.__dict__[name]
            elif name == 'callers':
                caller_wrappers = self._template.__dict__[name]
            else:
                setattr(self, name, self._template.__dict__[name])
        
        self._init_handlers(executor_wrappers)
        self._init_runners(caller_wrappers)

    def _init_handlers(self, wrappers: List[Tuple[IEventExecutor, IEventHandler, List[str]]]) -> None:
        if wrappers is None:
            return 
        self.handlers = []
        for executor, handler_class, params in wrappers:
            self.handlers.append(
                handler_class(executor, self, self._responder, *params)
            )

    def _init_runners(self, wrappers: List[Tuple[IHookCaller, IHookRunner, List[str]]]) -> None:
        if wrappers is None:
            return
        self.runners = []
        for caller, runner_class, params in wrappers:
            self.runners.append(
                runner_class(caller, self, self._responder)
            )


class PluginLoader:
    @classmethod
    def _load_main(cls, dir: str) -> ModuleType:
        """
        将插件目录下的入口文件，加载为模块
        """
        if not os.path.exists(os.path.join(dir, 'main.py')):
            raise BotException("缺乏入口主文件，插件无法加载")
        
        main_path = os.path.join(dir, 'main.py')
        spec = importlib.util.spec_from_file_location(os.path.basename(main_path), main_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    
    @classmethod
    def _load_template(cls, module: ModuleType) -> PluginTemplate:
        """
        从模块加载出插件模板对象
        """
        template_class = None
        for obj in module.__dict__.values():
            if isinstance(obj, type) and issubclass(obj, PluginTemplate) and obj.__name__ != 'PluginTemplate':
                template_class = obj
                break
        if template_class is None:
            raise BotException("不存在插件模版类，无法加载插件")
        return template_class()
    
    @classmethod
    def _template_verify(cls, template: PluginTemplate) -> None:
        """
        模板有效性校验
        """
        # TODO: 完善插件校验
        if template.name is None:
            raise BotException("插件必须有唯一标识的名称")

        if template.executors:
            for executor, handler_class, params in template.executors:
                if not iscoroutinefunction(executor):
                    raise BotException("事件执行方法必须为异步函数")
                
                ot_cb = params[-1]
                cw_cb = params[-2]
                if ot_cb is not None and not iscoroutinefunction(ot_cb):
                    raise BotException("回调方法必须为异步函数")
                if cw_cb is not None and not iscoroutinefunction(cw_cb):
                    raise BotException("回调方法必须为异步函数")
        
        if template.callers:
            for caller, runner_class, params in template.callers:
                if not iscoroutinefunction(caller):
                    raise BotException("事件执行方法必须为异步函数")

    @classmethod
    def load_plugin(cls, plugin_path: str, responder: IActionResponder) -> BotPlugin:
        module = cls._load_main(plugin_path)
        template = cls._load_template(module)
        cls._template_verify(template)
        return BotPlugin(plugin_path, template, responder)


_plugin_ctx = ContextVar("plugin_ctx")


class PluginLocal:
    """
    插件自动上下文对象
    """
    __slots__ = tuple(
        list(
            filter(lambda x: not (len(x) >= 2 and x[:2] == '__'), dir(BotPlugin))
        ) + ['__storage__']
    )

    def __init__(self) -> None:
        object.__setattr__(self, '__storage__', _plugin_ctx)
        self.__storage__: ContextVar[BotPlugin]
        # 对应 BotPlugin 的类型注解
        self.name: str
        self.dir: str
        self.version: str
        self.rw_auth: bool
        self.call_auth: bool
        self.store: Dict[str, Any]
        self.handlers: List[IEventHandler]
        self.runners: List[IHookRunner]

    def __setattr__(self, __name: str, __value: Any) -> None:
        setattr(self.__storage__.get(), __name, __value)

    def __getattr__(self, __name: str) -> Any:
        return getattr(self.__storage__.get(), __name)
    
    def _add_ctx(self, ctx: BotPlugin) -> Token:
        return self.__storage__.set(ctx)
    
    def _del_ctx(self, token: Token) -> None:
        self.__storage__.reset(token)

    def at_message(self, matcher: BotMatcher=None, parser: BotParser=None, checker: BotChecker=None, priority: int=PriorityLevel.MEAN.value, 
                   timeout: int=None, set_block: bool=False, temp: bool=False, session_rule: SessionRule=None, 
                   conflict_wait: bool=False, conflict_callback: Callable[[None], Coroutine]=None, 
                   overtime_callback: Callable[[None], Coroutine]=None
                   ) -> Callable:
        def make_wrapper(executor: IEventExecutor) -> Tuple[IEventExecutor, IEventHandler, List[str]]:
            return (executor, MsgEventHandler, [matcher, parser, checker, priority, timeout, set_block, temp, 
                                                session_rule, conflict_wait, conflict_callback, overtime_callback])
        return make_wrapper


PLUGIN_LOCAL = PluginLocal()


# TODO: 考虑事件处理器是否有更多部分可以放到基类中
class MsgEventHandler(IEventHandler):
    def __init__(self, executor: IEventExecutor, plugin_ref: BotPlugin, responder: IActionResponder, matcher: BotMatcher=None, 
                 parser: BotParser=None, checker: BotChecker=None, priority: int=PriorityLevel.MEAN.value, timeout: float=None, 
                 set_block: bool=False, temp: bool=False, session_rule: SessionRule=None, conflict_wait: bool=False, 
                 conflict_callback: Callable[[None], Coroutine]=None, overtime_callback: Callable[[None], Coroutine]=None
                 ) -> None:
        """
        matcher 和 parser 必须一个为 None, 另一存在。
        """
        super().__init__(priority, timeout, set_block, temp)

        self.executor = executor
        self.responder = responder
        self.matcher = matcher
        self.parser = parser
        self.checker = checker

        self._run_lock = aio.Lock()
        self._session_rule = session_rule
        self._plugin_ref = plugin_ref
        self._conflict_cb = conflict_callback
        self._overtime_cb = overtime_callback
        self._wait_flag = conflict_wait
        self._session_space: List[BotSession] = []
        self._session_lock = aio.Lock()
        # TODO: seesion 挂起的设计
        # self._suspended_sessions: List[BotSession] = []

        if (self.matcher is None and self.parser is None) or \
            (self.matcher and self.parser):
            raise BotValueError("matcher 和 parser 不能同时为空或同时存在")

    def _verify(self, event: MsgEvent) -> bool:
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
        
    async def _run_with_ctx(self, coro: Coroutine, session: BotSession=None, plugin_ref: BotPlugin=None, timeout: float=None) -> None:
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

    async def _run(self, event: MsgEvent) -> None:
        """
        获取 session 然后准备运行 executor
        """
        session = await BotSessionManager.get(event, self.responder, self._session_lock, self._session_rule, 
                                              self._session_space, self._wait_flag)
        if session is None: 
            if self._conflict_cb:
                temp_session = await BotSessionManager.get(event, self.responder)
                await self._run_with_ctx(self._conflict_cb(), temp_session, plugin_ref=self._plugin_ref)
            return
        
        await self._handle(session)
        BotSessionManager.recycle(session)

    async def evoke(self, event: MsgEvent) -> bool:
        """
        接收总线分发的事件的方法。返回校验结果，便于 disptacher 进行优先级阻断。校验通过会自动处理事件。
        """
        if not self.is_valid:
            return False

        if not self._verify(event):
            return False
        
        if not self.is_temp:
            aio.create_task(self._run(event))
            return True

        async with self._run_lock:
            if self.is_valid:
                aio.create_task(self._run(event))
                self.is_valid = False
                return True
            else:
                return False



class ReqEventHandler(IEventHandler):
    def __init__(self, executor: IEventExecutor, plugin_ref: BotPlugin, responder: IActionResponder, checker: BotChecker=None, 
                 priority: int=PriorityLevel.MEAN.value, timeout: float=None, set_block: bool=False, temp: bool=False, 
                 session_rule: SessionRule=None, conflict_wait: bool=False, conflict_callback: Callable[[None], Coroutine]=None, 
                 overtime_callback: Callable[[None], Coroutine]=None
                 ) -> None:
        super().__init__(priority, timeout, set_block, temp)

        self.executor = executor
        self.responder = responder
        self.checker = checker
        
        self._run_lock = aio.Lock()
        self._session_rule = session_rule
        self._plugin_ref = plugin_ref
        self._conflict_cb = conflict_callback
        self._overtime_cb = overtime_callback
        self._wait_flag = conflict_wait
        self._session_space = []
        self._session_lock = aio.Lock()

    def _verify(self, event: BotEvent) -> bool:
        if self.checker:
            return self.checker.check(event)
        else:
            return True
        
    async def _run_with_ctx(self, coro: Coroutine, session: BotSession=None, plugin_ref: BotPlugin=None, timeout: float=None) -> None:
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

    async def _run(self, event: RequestEvent) -> None:
        """
        获取 session 然后准备运行 executor
        """
        session = await BotSessionManager.get(event, self.responder, self._session_lock, self._session_rule, 
                                              self._session_space, self._wait_flag)
        if session is None: 
            if self._conflict_cb:
                temp_session = await BotSessionManager.get(event, self.responder)
                await self._run_with_ctx(self._conflict_cb(), temp_session, plugin_ref=self._plugin_ref)
            return
        
        await self._handle(session)
        BotSessionManager.recycle(session)

    async def evoke(self, event: RequestEvent) -> bool:
        """
        接收总线分发的事件的方法。返回校验结果，便于 disptacher 进行优先级阻断。校验通过会自动处理事件。
        """
        if not self.is_valid:
            return False

        if not self._verify(event):
            return False
        
        if not self.is_temp:
            aio.create_task(self._run(event))
            return True

        async with self._run_lock:
            if self.is_valid:
                aio.create_task(self._run(event))
                self.is_valid = False
                return True
            else:
                return False


class NoticeEventHandler(IEventHandler):
    def __init__(self, executor: IEventExecutor, plugin_ref: BotPlugin, responder: IActionResponder, checker: BotChecker=None, 
                 priority: int=PriorityLevel.MEAN.value, timeout: float=None, set_block: bool=False, temp: bool=False, 
                 session_rule: SessionRule=None, conflict_wait: bool=False, conflict_callback: Callable[[None], Coroutine]=None, 
                 overtime_callback: Callable[[None], Coroutine]=None
                 ) -> None:
        super().__init__(priority, timeout, set_block, temp)

        self.executor = executor
        self.responder = responder
        self.checker = checker

        self._run_lock = aio.Lock()
        self._session_rule = session_rule
        self._plugin_ref = plugin_ref
        self._conflict_cb = conflict_callback
        self._overtime_cb = overtime_callback
        self._wait_flag = conflict_wait
        self._session_space = []
        self._session_lock = aio.Lock()

    def _verify(self, event: BotEvent) -> bool:
        if self.checker:
            return self.checker.check(event)
        else:
            return True
        
    async def _run_with_ctx(self, coro: Coroutine, session: BotSession=None, plugin_ref: BotPlugin=None, timeout: float=None) -> None:
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

    async def _run(self, event: NoticeEvent) -> None:
        """
        获取 session 然后准备运行 executor
        """
        session = await BotSessionManager.get(event, self.responder, self._session_lock, self._session_rule, 
                                              self._session_space, self._wait_flag)
        if session is None: 
            if self._conflict_cb:
                temp_session = await BotSessionManager.get(event, self.responder)
                await self._run_with_ctx(self._conflict_cb(), temp_session, plugin_ref=self._plugin_ref)
            return
        
        await self._handle(session)
        BotSessionManager.recycle(session)

    async def evoke(self, event: NoticeEvent) -> bool:
        """
        接收总线分发的事件的方法。返回校验结果，便于 disptacher 进行优先级阻断。校验通过会自动处理事件。
        """
        if not self.is_valid:
            return False

        if not self._verify(event):
            return False
        
        if not self.is_temp:
            aio.create_task(self._run(event))
            return True

        async with self._run_lock:
            if self.is_valid:
                aio.create_task(self._run(event))
                self.is_valid = False
                return True
            else:
                return False
