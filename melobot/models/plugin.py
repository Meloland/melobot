import asyncio as aio
import inspect
import traceback
from asyncio import iscoroutinefunction
from pathlib import PosixPath

from .event import MsgEvent
from .session import SESSION_LOCAL, BotSession, BotSessionManager, SessionRule
from .ipc import PluginStore, PluginSignalHandler, PluginBus
from .bot import HookRunner, BotHookBus
from ..interface.exceptions import *
from ..interface.core import IActionResponder
from ..interface.utils import BotChecker, BotMatcher, BotParser, Logger
from ..interface.typing import *
from ..interface.models import IEventHandler, HandlerArgs, HookRunnerArgs, ShareObjArgs, \
                                ShareCbArgs, SignalHandlerArgs, PluginProxy


class Plugin:
    """
    bot 插件基类。所有自定义插件必须继承该类实现。
    """

    # 标记了该类有哪些实例属性需要被共享。每个元素是一个共享对象构造参数元组
    __share__: List[ShareObjArgs] = []

    def __init__(self) -> None:
        self.id: str=None
        self.version: str='1.0.0'
        self.handlers: List[IEventHandler] = []
        self.root_path: PosixPath
        self.proxy: PluginProxy

    def _init_(self, root_path: PosixPath, logger: Logger, responder: IActionResponder) -> None:
        """
        初始化当前插件
        """
        self.root_path = root_path
        if self.id is None:
            raise BotException("未初始化插件 id，或其为 None")
        members = inspect.getmembers(self)

        for attr_name, val in members:
            if isinstance(val, HandlerArgs):
                executor, handler_class, params = val
                if not iscoroutinefunction(executor):
                    raise BotException("事件处理器必须为异步方法")
                overtime_cb, conflict_cb = params[-1], params[-2]
                if overtime_cb and not iscoroutinefunction(overtime_cb):
                    raise BotException("超时回调方法必须为异步函数")
                if conflict_cb and not iscoroutinefunction(conflict_cb):
                    raise BotException("冲突回调方法必须为异步函数")
                handler = handler_class(executor, self, responder, logger, *params)
                self.handlers.append(handler)
                BotSessionManager.register(handler)

            elif isinstance(val, HookRunnerArgs):
                hook_func, type = val
                if not iscoroutinefunction(hook_func):
                    raise BotException("hook 方法必须为异步函数")
                runner = HookRunner(type, hook_func, self)
                BotHookBus._register(type, runner)
            
            elif isinstance(val, ShareCbArgs):
                namespace, id, cb = val
                if not iscoroutinefunction(cb):
                    raise BotException("共享对象的回调必须为异步函数")
                PluginStore._bind_cb(namespace, id, cb, self)
            
            elif isinstance(val, SignalHandlerArgs):
                func, type = val
                if not iscoroutinefunction(func):
                    raise BotException("信号处理方法必须为异步函数")
                handler = PluginSignalHandler(type, func, self)
                PluginBus._register(type, handler)
        
        for val in self.__class__.__share__:
            attrs_map = {k: v for k, v in inspect.getmembers(self) if not k.startswith('__')}
            property, namespace, id = val
            if attrs_map.get(property) is None and property is not None:
                raise BotException("尝试共享一个不存在的属性")
            PluginStore._activate_so(property, namespace, id, self)

        self.proxy = PluginProxy(self)

    @classmethod
    def on(cls, signal_name: str) -> Callable:
        """
        使用该装饰器，注册一个插件信号处理器
        """
        def make_args(func: AsyncFunc[None]) -> SignalHandlerArgs:
            return SignalHandlerArgs(func=func, type=signal_name)
        return make_args

    @classmethod
    def on_message(cls, matcher: BotMatcher=None, parser: BotParser=None, checker: BotChecker=None, priority: int=PriorityLevel.MEAN.value, 
                   timeout: int=None, block: bool=False, temp: bool=False, session_rule: SessionRule=None, session_hold: bool=False, 
                   direct_rouse: bool=False, conflict_wait: bool=False, conflict_callback: Callable[[None], Coroutine]=None, 
                   overtime_callback: Callable[[None], Coroutine]=None
                   ) -> Callable:
        """
        使用该装饰器，将方法标记为消息事件执行器
        """
        def make_args(executor: AsyncFunc[None]) -> HandlerArgs:
            return HandlerArgs(executor=executor,
                              type=MsgEventHandler,
                              params=[matcher, parser, checker, priority, timeout, block, temp, 
                                      session_rule, session_hold, direct_rouse, conflict_wait, conflict_callback, overtime_callback])
        return make_args


# TODO: 考虑事件处理器是否有更多部分可以放到基类中
class MsgEventHandler(IEventHandler):
    def __init__(self, executor: AsyncFunc[None], plugin: Plugin, responder: IActionResponder, logger: Logger, 
                 matcher: BotMatcher=None, parser: BotParser=None, checker: BotChecker=None, priority: int=PriorityLevel.MEAN.value, timeout: float=None, 
                 set_block: bool=False, temp: bool=False, session_rule: SessionRule=None, session_hold: bool=False, direct_rouse: bool=False, 
                 conflict_wait: bool=False, conflict_callback: Callable[[None], Coroutine]=None, overtime_callback: Callable[[None], Coroutine]=None
                 ) -> None:
        super().__init__(priority, timeout, set_block, temp)

        self.executor = executor
        self.responder = responder
        self.logger = logger
        self.matcher = matcher
        self.parser = parser
        self.checker = checker

        self._run_lock = aio.Lock()
        self._rule = session_rule
        self._hold = session_hold
        self._plugin = plugin
        self._direct_rouse = direct_rouse
        self._conflict_cb = conflict_callback
        self._overtime_cb = overtime_callback
        self._wait_flag = conflict_wait

        # matcher 和 parser 必须一个为 None, 另一存在
        if (matcher is None and parser is None) or (matcher and parser):
            raise BotValueError("参数 matcher 和 parser 不能同时为空或同时存在")
        
        if session_rule is None:
            if session_hold or direct_rouse or conflict_wait or conflict_callback:
                raise BotException("以下的参数必须和 session_rule 参数一同使用：session_hold， direct_rouse, \
                                   conflict_wait, conflict_callback")
        
        if conflict_wait and conflict_callback:
            raise BotException("参数 conflict_wait 为 True 时，conflict_callback 永远不会被调用")

    def _verify(self, event: MsgEvent) -> bool:
        """
        验证事件是否有触发执行的资格（验权）
        """
        if self.checker:
            return self.checker.check(event)
        return True

    def _match(self, event: MsgEvent) -> bool:
        """
        通过验权后，尝试对事件进行文本匹配
        """
        if self.matcher:
            return self.matcher.match(event)
        if self.parser:
            args = self.parser.parse(event)
            if args is not None:
                event._store_args(self, args)
                return True
            else:
                return False

    async def _run_on_ctx(self, coro: Coroutine, session: BotSession=None, timeout: float=None) -> None:
        """
        在指定 session 上下文中运行协程。异常将会抛出
        """
        if not hasattr(session, '_handler'):
            BotSessionManager.inject(session, self)
        try:
            s_token = SESSION_LOCAL._add_ctx(session)
            await aio.wait_for(aio.create_task(coro), timeout=timeout)
        finally:
            SESSION_LOCAL._del_ctx(s_token)

    async def _run(self, event: MsgEvent) -> None:
        """
        获取 session 然后准备运行 executor
        """
        try:
            session = None
            if not self._direct_rouse:
                res = await BotSessionManager.try_attach(event, self)
                if res:
                    return
            session = await BotSessionManager.get(event, self.responder, self)
            # 如果因为冲突没有获得 session，且指定了冲突回调
            if session is None and self._conflict_cb:
                temp_session = BotSessionManager.make_temp(event, self.responder)
                await self._run_on_ctx(self._conflict_cb(), temp_session)
            # 如果因为冲突没有获得 session，但没有冲突回调
            if session is None:
                return
            # 如果没有冲突，正常获得到了 session
            try:
                exec_coro = self.executor(self._plugin)
                await self._run_on_ctx(exec_coro, session, self.timeout)
            except aio.TimeoutError:
                if self._overtime_cb:
                    await self._run_on_ctx(self._overtime_cb(), session)
        except Exception as e:
            e_name = e.__class__.__name__
            executor_name = self.executor.__qualname__
            self.logger.error(f"插件 {self._plugin.id} 事件处理方法 {executor_name} 发生异常：[{e_name}] {e}")
            self.logger.debug(f"异常点的事件记录为：{event.raw}")
            self.logger.debug('异常回溯栈：\n' + traceback.format_exc().strip('\n'))
        finally:
            if session is None:
                return
            BotSessionManager.recycle(session, alive=self._hold)

    async def evoke(self, event: MsgEvent) -> bool:
        """
        接收总线分发的事件的方法。返回是否决定处理的判断。
        便于 disptacher 进行优先级阻断。校验通过会自动处理事件。
        """
        if not self._verify(event):
            return False

        if self._direct_rouse:
            res = await BotSessionManager.try_attach(event, self)
            if res:
                return True

        if not self.is_valid:
            return False

        if not self._match(event):
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
    pass


class NoticeEventHandler(IEventHandler):
    pass