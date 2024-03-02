import inspect
from asyncio import iscoroutinefunction
from pathlib import Path

from ..types.core import IActionResponder
from ..types.exceptions import *
from ..types.models import (
    HandlerArgs,
    HookRunnerArgs,
    IEventHandler,
    ShareCbArgs,
    ShareObjArgs,
    SignalHandlerArgs,
)
from ..types.typing import *
from ..types.utils import BotChecker, BotMatcher, BotParser, Logger, WrappedLogger
from ..utils.checker import AtChecker
from .bot import BotHookBus, HookRunner, PluginProxy
from .handler import MsgEventHandler, NoticeEventHandler, ReqEventHandler, MetaEventHandler
from .ipc import PluginBus, PluginSignalHandler, PluginStore
from .session import BotSessionManager, SessionRule


class Plugin:
    """
    bot 插件基类。所有自定义插件必须继承该类实现。
    """

    # 标记了该类有哪些实例属性需要被共享。每个元素是一个共享对象构造参数元组
    __share__: List[ShareObjArgs] = []
    # 插件 id 和 version 标记
    __id__: str = None
    __version__: str = "1.0.0"
    # 插件类所在的文件路径，PosicPath 对象
    ROOT: Path
    # 被二次包装的全局日志器
    LOGGER: WrappedLogger

    def __init__(self) -> None:
        self.__handlers: List[IEventHandler]
        self.__proxy: PluginProxy

    def __build(
        self, root_path: Path, logger: Logger, responder: IActionResponder
    ) -> None:
        """
        初始化当前插件
        """
        if self.__class__.__id__ is None:
            self.__class__.__id__ = self.__class__.__name__
        for idx, val in enumerate(self.__class__.__share__):
            if isinstance(val, str):
                self.__class__.__share__[idx] = val, self.__class__.__name__, val
        self.__handlers = []

        self.__class__.ROOT = root_path
        self.__class__.LOGGER = WrappedLogger(logger, self.__class__.__id__)

        attrs_map = {
            k: v for k, v in inspect.getmembers(self) if not k.startswith("__")
        }
        for val in self.__class__.__share__:
            property, namespace, id = val
            if property not in attrs_map.keys() and property is not None:
                raise BotRuntimeError(
                    f"插件 {self.__class__.__name__} 尝试共享一个不存在的属性 {property}"
                )
            PluginStore._create_so(property, namespace, id, self)

        members = inspect.getmembers(self)
        for attr_name, val in members:
            if isinstance(val, HandlerArgs):
                executor, handler_class, params = val
                if not iscoroutinefunction(executor):
                    raise BotTypeError(f"事件处理器 {executor.__name__} 必须为异步方法")
                overtime_cb_maker, conflict_cb_maker = params[-1], params[-2]
                if overtime_cb_maker and not callable(overtime_cb_maker):
                    raise BotTypeError(
                        f"超时回调方法 {overtime_cb_maker.__name__} 必须为可调用对象"
                    )
                if conflict_cb_maker and not callable(conflict_cb_maker):
                    raise BotTypeError(
                        f"冲突回调方法 {conflict_cb_maker.__name__} 必须为可调用对象"
                    )
                handler = handler_class(executor, self, responder, logger, *params)
                self.__handlers.append(handler)
                BotSessionManager.register(handler)

            elif isinstance(val, HookRunnerArgs):
                hook_func, type = val
                if not iscoroutinefunction(hook_func):
                    raise BotTypeError(f"hook 方法 {hook_func.__name__} 必须为异步函数")
                runner = HookRunner(type, hook_func, self)
                BotHookBus._register(type, runner)

            elif isinstance(val, ShareCbArgs):
                namespace, id, cb = val
                if not iscoroutinefunction(cb):
                    raise BotTypeError(
                        f"{namespace} 命名空间中，id 为 {id} 的共享对象，它的回调 {cb.__name__} 必须为异步函数"
                    )
                PluginStore._bind_cb(namespace, id, cb, self)

            elif isinstance(val, SignalHandlerArgs):
                func, namespace, signal = val
                if not iscoroutinefunction(func):
                    raise BotTypeError(f"信号处理方法 {func.__name__} 必须为异步函数")
                handler = PluginSignalHandler(namespace, signal, func, self)
                PluginBus._register(namespace, signal, handler)

        self.__proxy = PluginProxy(self)

    @classmethod
    def on_msg(
        cls,
        matcher: BotMatcher = None,
        parser: BotParser = None,
        checker: BotChecker = None,
        priority: PriorityLevel = PriorityLevel.MEAN,
        timeout: int = None,
        block: bool = False,
        temp: bool = False,
        session_rule: SessionRule = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Callable[[None], Coroutine] = None,
        overtime_cb: Callable[[None], Coroutine] = None,
    ) -> Callable:
        """
        使用该装饰器，将方法标记为消息事件执行器
        """

        def make_args(executor: AsyncFunc[None]) -> HandlerArgs:
            return HandlerArgs(
                executor=executor,
                type=MsgEventHandler,
                params=[
                    matcher,
                    parser,
                    checker,
                    priority,
                    timeout,
                    block,
                    temp,
                    session_rule,
                    session_hold,
                    direct_rouse,
                    conflict_wait,
                    conflict_cb,
                    overtime_cb,
                ],
            )

        return make_args

    @classmethod
    def on_any_msg(
        cls,
        checker: BotChecker = None,
        priority: PriorityLevel = PriorityLevel.MEAN,
        timeout: int = None,
        block: bool = False,
        temp: bool = False,
        session_rule: SessionRule = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Callable[[None], Coroutine] = None,
        overtime_cb: Callable[[None], Coroutine] = None,
    ) -> Callable:
        """
        使用该装饰器，将方法标记为消息事件执行器。
        任何消息经过校验后，不进行匹配和解析即可触发处理方法
        """

        def make_args(executor: AsyncFunc[None]) -> HandlerArgs:
            return HandlerArgs(
                executor=executor,
                type=MsgEventHandler,
                params=[
                    None,
                    None,
                    checker,
                    priority,
                    timeout,
                    block,
                    temp,
                    session_rule,
                    session_hold,
                    direct_rouse,
                    conflict_wait,
                    conflict_cb,
                    overtime_cb,
                ],
            )

        return make_args

    @classmethod
    def on_at_msg(
        cls,
        qid: int = None,
        matcher: BotMatcher = None,
        parser: BotParser = None,
        checker: BotChecker = None,
        priority: PriorityLevel = PriorityLevel.MEAN,
        timeout: int = None,
        block: bool = False,
        temp: bool = False,
        session_rule: SessionRule = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Callable[[None], Coroutine] = None,
        overtime_cb: Callable[[None], Coroutine] = None,
    ) -> Callable:
        at_checker = AtChecker(qid)
        if checker is not None:
            the_checker = at_checker & checker
        else:
            the_checker = at_checker

        def make_args(executor: AsyncFunc[None]) -> HandlerArgs:
            return HandlerArgs(
                executor=executor,
                type=MsgEventHandler,
                params=[
                    matcher,
                    parser,
                    the_checker,
                    priority,
                    timeout,
                    block,
                    temp,
                    session_rule,
                    session_hold,
                    direct_rouse,
                    conflict_wait,
                    conflict_cb,
                    overtime_cb,
                ],
            )

        return make_args
