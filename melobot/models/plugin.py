import asyncio as aio
import inspect
import traceback
from asyncio import iscoroutinefunction

from .event import MsgEvent
from .session import SESSION_LOCAL, BotSession, BotSessionManager, SessionRule
from ..interface.exceptions import *
from ..interface.core import IActionResponder
from ..interface.utils import BotChecker, BotMatcher, BotParser, Logger
from ..interface.typing import *
from ..interface.models import IEventHandler, IHookRunner, IEventExecutor, IHookFunc, HandlerCons, RunnerCons


class Plugin:
    """
    bot 插件基类。所有自定义插件必须继承该类实现。
    """
    def __init__(self) -> None:
        self.id: str=None
        self.version: str='1.0.0'
        self.dir: str
        self.handlers: List[IEventHandler]
        self.runners: List[IHookRunner]

        self._executors: List[IEventExecutor]=[]
        self._hooks: List[IHookFunc]=[]

    def _init(self) -> None:
        """
        初始化方法。建立 executors 和 hooks
        """
        members = inspect.getmembers(self)
        for attr_name, attr in members:
            if isinstance(attr, HandlerCons):
                self._executors.append(attr)
            elif isinstance(attr, RunnerCons):
                self._hooks.append(attr)

    def _attr_check(self) -> None:
        """
        插件参数检查，在 handlers 和 runners 构建前运行。
        """
        if self.id is None:
            raise BotException("未初始化插件名称（id），或其为 None")
        
        for executor, handler_class, params in self._executors:
            if not iscoroutinefunction(executor):
                raise BotException("事件处理器必须为异步方法")
            
            overtime_cb, conflict_cb = params[-1], params[-2]
            if overtime_cb and not iscoroutinefunction(overtime_cb):
                raise BotException("超时回调方法必须为异步函数")
            if conflict_cb and not iscoroutinefunction(conflict_cb):
                raise BotException("冲突回调方法必须为异步函数")

        for hook_func, runner_class, params in self._hooks:
            if not iscoroutinefunction(hook_func):
                raise BotException("hook 方法必须为异步函数")

    def _build(self, dir: str, logger: Logger, resonder: IActionResponder) -> None:
        """
        plugin 的依赖注入。与 handlers，runners 的构建
        """
        self.dir = dir

        self.handlers = []
        for executor, handler_class, params in self._executors:
            handler = handler_class(executor, self, resonder, logger, *params)
            self.handlers.append(handler)
            BotSessionManager.register(handler)
        self.runners = []
        for hook_func, runner_class, params in self._hooks:
            self.runners.append(runner_class(hook_func, self, resonder, logger, *params))

    def build(self, dir: str, logger: Logger, responder: IActionResponder) -> None:
        """
        供外部调用的插件内部建立方法
        """
        self._init()
        self._attr_check()
        self._build(dir, logger, responder)

    @classmethod
    def on_message(cls, matcher: BotMatcher=None, parser: BotParser=None, checker: BotChecker=None, priority: int=PriorityLevel.MEAN.value, 
                   timeout: int=None, block: bool=False, temp: bool=False, session_rule: SessionRule=None, session_hold: bool=False, 
                   direct_rouse: bool=False, conflict_wait: bool=False, conflict_callback: Callable[[None], Coroutine]=None, 
                   overtime_callback: Callable[[None], Coroutine]=None
                   ) -> Callable:
        """
        使用该装饰器，将方法标记为消息事件执行器
        """
        def make_constructor(executor: IEventExecutor) -> HandlerCons:
            return HandlerCons(executor=executor,
                              type=MsgEventHandler,
                              params=[matcher, parser, checker, priority, timeout, block, temp, 
                                      session_rule, session_hold, direct_rouse, conflict_wait, conflict_callback, overtime_callback])
        return make_constructor


# TODO: 考虑事件处理器是否有更多部分可以放到基类中
class MsgEventHandler(IEventHandler):
    def __init__(self, executor: IEventExecutor, plugin_ref: Plugin, responder: IActionResponder, logger: Logger, matcher: BotMatcher=None, 
                 parser: BotParser=None, checker: BotChecker=None, priority: int=PriorityLevel.MEAN.value, timeout: float=None, 
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
        self._plugin_ref = plugin_ref
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
        if not hasattr(session, '_handler_ref'):
            BotSessionManager.bind(session, self)
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
                temp_session = await BotSessionManager.make_temp(event, self.responder)
                await self._run_on_ctx(self._conflict_cb(), temp_session)
            # 如果因为冲突没有获得 session，但没有冲突回调
            if session is None:
                return
            # 如果没有冲突，正常获得到了 session
            try:
                exec_coro = self.executor(self._plugin_ref)
                await self._run_on_ctx(exec_coro, session, self.timeout)
            except aio.TimeoutError:
                if self._overtime_cb:
                    await self._run_on_ctx(self._overtime_cb(), session)
        except Exception as e:
            e_name = e.__class__.__name__
            executor_name = self.executor.__qualname__
            self.logger.error(f"插件 {self._plugin_ref.id} 事件处理方法 {executor_name} 发生异常：[{e_name}] {e}")
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