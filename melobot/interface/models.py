import asyncio as aio
import inspect
import traceback
from abc import ABC, abstractmethod
from asyncio import iscoroutinefunction

from ..models.event import BotEvent, MsgEvent, NoticeEvent, RequestEvent
from ..models.session import SESSION_LOCAL, BotSession, BotSessionManager, SessionRule
from ..models.event import BotEvent
from ..utils.logger import Logger
from ..utils.parser import ParseArgs
from .exceptions import *
from .core import IActionResponder
from .utils import BotChecker, BotMatcher, BotParser
from .typing import *


class IEventHandler(ABC):
    def __init__(self, priority: int=1, timeout: float=None, set_block: bool=False, temp: bool=False) -> None:
        super().__init__()
        self.set_block = set_block
        self.timeout = timeout
        self.priority = priority

        self.is_temp = temp
        self.is_valid = True

    @abstractmethod
    def _verify(self, event: BotEvent) -> bool:
        """
        前置校验逻辑，包含权限校验、尝试匹配和尝试解析
        """
        pass

    @abstractmethod
    async def evoke(self, event: BotEvent) -> bool:
        """
        接收总线分发的事件的方法。返回校验结果，便于 disptacher 进行优先级阻断。校验通过会自动处理事件。
        """
        pass


class IHookRunner(ABC):
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    async def run(self) -> None:
        pass


# 事件方法（事件执行器）
IEventExecutor = Callable[[None], Coroutine[Any, Any, None]]
# 钩子方法（插件钩子）
IHookFunc = Callable[[None], Coroutine[Any, Any, None]]
# 事件方法（事件执行器）构造器
HandlerCons = NamedTuple('ExecutorCons', executor=IEventExecutor, type=IEventHandler, params=List[Any])
# 钩子方法（插件钩子）构造器
RunnerCons = NamedTuple('HookCons', hook_func=IHookFunc, type=IHookRunner, params=List[Any])


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
                   timeout: int=None, set_block: bool=False, temp: bool=False, session_rule: SessionRule=None, 
                   conflict_wait: bool=False, conflict_callback: Callable[[None], Coroutine]=None, 
                   overtime_callback: Callable[[None], Coroutine]=None
                   ) -> Callable:
        """
        使用该装饰器，将方法标记为消息事件执行器
        """
        def make_constructor(executor: IEventExecutor) -> HandlerCons:
            return HandlerCons(executor=executor,
                              type=MsgEventHandler,
                              params=[matcher, parser, checker, priority, timeout, set_block, temp, 
                                      session_rule, conflict_wait, conflict_callback, overtime_callback])
        return make_constructor


# TODO: 考虑事件处理器是否有更多部分可以放到基类中
class MsgEventHandler(IEventHandler):
    def __init__(self, executor: IEventExecutor, plugin_ref: Plugin, responder: IActionResponder, logger: Logger, matcher: BotMatcher=None, 
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
        self.logger = logger
        self.matcher = matcher
        self.parser = parser
        self.checker = checker

        self._run_lock = aio.Lock()
        self._session_rule = session_rule
        self._plugin_ref = plugin_ref
        self._conflict_cb = conflict_callback
        self._overtime_cb = overtime_callback
        self._wait_flag = conflict_wait

        # self._verify 时可能产生，如果存在则在 session 构建阶段移除，转移到 session 去存储
        self._args_buf: Dict[BotEvent, ParseArgs] = {}

        if (self.matcher is None and self.parser is None) or \
            (self.matcher and self.parser):
            raise BotValueError("matcher 和 parser 不能同时为空或同时存在")
    
    def _pop_args(self, event: BotEvent) -> Union[ParseArgs, None]:
        """
        尝试从 buf 中 pop args。如果不存在，则返回 None
        """
        return self._args_buf.pop(event, None)

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
            if args is not None:
                self._args_buf[event] = args
                return True
            return False
        
    async def _handle_on_ctx(self, coro: Coroutine, session: BotSession=None, plugin_ref: Plugin=None, timeout: float=None) -> None:
        """
        在指定上下文下运行。异常将会抛出
        """
        try:
            s_token = SESSION_LOCAL._add_ctx(session)
            await aio.wait_for(aio.create_task(coro), timeout=timeout)
        finally:
            SESSION_LOCAL._del_ctx(s_token)

    async def _handle(self, session: BotSession) -> None:
        """
        正式开始运行 executor
        """
        try:
            exec_coro: Coroutine = self.executor(self._plugin_ref)
            await self._handle_on_ctx(exec_coro, session, self._plugin_ref, self.timeout)
        except aio.TimeoutError:
            if self._overtime_cb:
                await self._handle_on_ctx(self._overtime_cb(), session, self._plugin_ref)

    async def _run(self, event: MsgEvent) -> None:
        """
        获取 session 然后准备运行 executor
        """
        try:
            session = await BotSessionManager.get(event, self.responder, self)
            if session is None and self._conflict_cb:
                temp_session = await BotSessionManager.get(event, self.responder, self, forbid_rule=True)
                await self._handle_on_ctx(self._conflict_cb(), temp_session, self._plugin_ref)
            """
            此时需要额外清理可能存在的 event 对应的解析参数。
            因为执行到这里，可能上面的 temp_session 取走了解析参数，也有可能没有 _conflict_cb，
            导致没有 session 取走解析参数，因此直接再 pop 一次
            """
            if session is None:
                self._pop_args(event)
                return
            if isinstance(session, str):
                return
            await self._handle(session)
        except Exception as e:
            e_name = e.__class__.__name__
            executor_name = self.executor.__qualname__
            self.logger.error(f"插件 {self._plugin_ref.id} 事件处理方法 {executor_name} 发生异常：[{e_name}] {e}")
            self.logger.debug(f"异常点的事件记录为：{event.raw}")
            self.logger.debug('异常回溯栈：\n' + traceback.format_exc().strip('\n'))
        finally:
            if session and not isinstance(session, str):
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
    pass


class NoticeEventHandler(IEventHandler):
    pass

