import inspect
from asyncio import iscoroutinefunction
from pathlib import Path

from ..models.handler import EventHandler, EventHandlerArgs
from ..types.core import AbstractResponder
from ..types.exceptions import *
from ..types.models import (
    HookRunnerArgs,
    SessionRule,
    ShareCbArgs,
    ShareObjArgs,
    SignalHandlerArgs,
)
from ..types.typing import *
from ..types.utils import (
    BotChecker,
    BotMatcher,
    BotParser,
    Logger,
    LogicMode,
    PrefixLogger,
)
from ..utils.checker import (
    AtChecker,
    FriendReqChecker,
    GroupReqChecker,
    NoticeTypeChecker,
)
from ..utils.matcher import ContainMatch, EndMatch, FullMatch, RegexMatch, StartMatch
from .bot import BotHookBus, HookRunner, PluginProxy
from .handler import (
    MetaEventHandler,
    MsgEventHandler,
    NoticeEventHandler,
    ReqEventHandler,
)
from .ipc import PluginBus, PluginSignalHandler, PluginStore
from .session import BotSessionManager


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
    LOGGER: PrefixLogger

    def __init__(self) -> None:
        self.__handlers: List[EventHandler]
        self.__proxy: PluginProxy

    def __build(
        self, root_path: Path, logger: Logger, responder: AbstractResponder
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
        self.__class__.LOGGER = PrefixLogger(logger, self.__class__.__id__)

        attrs_map = {
            k: v for k, v in inspect.getmembers(self) if not k.startswith("__")
        }
        for val in self.__class__.__share__:
            property, namespace, id = val
            if property not in attrs_map.keys() and property is not None:
                raise PluginBuildError(
                    f"插件 {self.__class__.__name__} 尝试共享一个不存在的属性 {property}"
                )
            PluginStore._create_so(property, namespace, id, self)

        members = inspect.getmembers(self)
        for attr_name, val in members:
            if isinstance(val, EventHandlerArgs):
                executor, handler_class, params = val
                if not iscoroutinefunction(executor):
                    raise PluginBuildError(
                        f"事件处理器 {executor.__name__} 必须为异步方法"
                    )
                overtime_cb_maker, conflict_cb_maker = params[-1], params[-2]
                if overtime_cb_maker and not callable(overtime_cb_maker):
                    raise PluginBuildError(
                        f"超时回调方法 {overtime_cb_maker.__name__} 必须为可调用对象"
                    )
                if conflict_cb_maker and not callable(conflict_cb_maker):
                    raise PluginBuildError(
                        f"冲突回调方法 {conflict_cb_maker.__name__} 必须为可调用对象"
                    )
                handler = handler_class(executor, self, responder, logger, *params)
                self.__handlers.append(handler)
                BotSessionManager.register(handler)

            elif isinstance(val, HookRunnerArgs):
                hook_func, type = val
                if not iscoroutinefunction(hook_func):
                    raise PluginBuildError(
                        f"hook 方法 {hook_func.__name__} 必须为异步函数"
                    )
                runner = HookRunner(type, hook_func, self)
                BotHookBus._register(type, runner)

            elif isinstance(val, ShareCbArgs):
                namespace, id, cb = val
                if not iscoroutinefunction(cb):
                    raise PluginBuildError(
                        f"{namespace} 命名空间中，id 为 {id} 的共享对象，它的回调 {cb.__name__} 必须为异步函数"
                    )
                PluginStore._bind_cb(namespace, id, cb, self)

            elif isinstance(val, SignalHandlerArgs):
                func, namespace, signal = val
                if not iscoroutinefunction(func):
                    raise PluginBuildError(
                        f"信号处理方法 {func.__name__} 必须为异步函数"
                    )
                handler = PluginSignalHandler(namespace, signal, func, self)
                PluginBus._register(namespace, signal, handler)

        self.__proxy = PluginProxy(self)

    @classmethod
    def on_message(
        cls,
        matcher: BotMatcher = None,
        parser: BotParser = None,
        checker: BotChecker = None,
        priority: PriorLevel = PriorLevel.MEAN,
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

        def make_args(executor: AsyncFunc[None]) -> EventHandlerArgs:
            return EventHandlerArgs(
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
    def on_every_message(
        cls,
        checker: BotChecker = None,
        priority: PriorLevel = PriorLevel.MEAN,
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
        使用该装饰器，将方法标记为任意消息事件执行器。
        任何消息经过校验后，不进行匹配和解析即可触发处理方法
        """

        def make_args(executor: AsyncFunc[None]) -> EventHandlerArgs:
            return EventHandlerArgs(
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
    def on_at_qq(
        cls,
        qid: int = None,
        matcher: BotMatcher = None,
        parser: BotParser = None,
        checker: BotChecker = None,
        priority: PriorLevel = PriorLevel.MEAN,
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
        使用该装饰器，将方法标记为艾特消息匹配的消息事件执行器。
        必须首先是来自指定 qid 的艾特消息，才能被进一步处理
        """
        at_checker = AtChecker(qid)
        if checker is not None:
            wrapped_checker = at_checker & checker
        else:
            wrapped_checker = at_checker

        def make_args(executor: AsyncFunc[None]) -> EventHandlerArgs:
            return EventHandlerArgs(
                executor=executor,
                type=MsgEventHandler,
                params=[
                    matcher,
                    parser,
                    wrapped_checker,
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
    def on_start_match(
        cls,
        target: str | list[str],
        logic_mode: LogicMode = LogicMode.OR,
        checker: BotChecker = None,
        priority: PriorLevel = PriorLevel.MEAN,
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
        使用该装饰器，将方法标记为字符串起始匹配的消息事件执行器。
        必须首先含有以 target 起始的文本，才能被进一步处理
        """
        start_matcher = StartMatch(target, logic_mode)

        def make_args(executor: AsyncFunc[None]) -> EventHandlerArgs:
            return EventHandlerArgs(
                executor=executor,
                type=MsgEventHandler,
                params=[
                    start_matcher,
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
    def on_contain_match(
        cls,
        target: str | list[str],
        logic_mode: LogicMode = LogicMode.OR,
        checker: BotChecker = None,
        priority: PriorLevel = PriorLevel.MEAN,
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
        使用该装饰器，将方法标记为字符串包含匹配的消息事件执行器。
        文本必须首先包含 target，才能被进一步处理
        """
        contain_matcher = ContainMatch(target, logic_mode)

        def make_args(executor: AsyncFunc[None]) -> EventHandlerArgs:
            return EventHandlerArgs(
                executor=executor,
                type=MsgEventHandler,
                params=[
                    contain_matcher,
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
    def on_full_match(
        cls,
        target: str | list[str],
        logic_mode: LogicMode = LogicMode.OR,
        checker: BotChecker = None,
        priority: PriorLevel = PriorLevel.MEAN,
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
        使用该装饰器，将方法标记为字符串相等匹配的消息事件执行器。
        文本必须首先与 target 内容完全一致，才能被进一步处理
        """
        full_matcher = FullMatch(target, logic_mode)

        def make_args(executor: AsyncFunc[None]) -> EventHandlerArgs:
            return EventHandlerArgs(
                executor=executor,
                type=MsgEventHandler,
                params=[
                    full_matcher,
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
    def on_end_match(
        cls,
        target: str | list[str],
        logic_mode: LogicMode = LogicMode.OR,
        checker: BotChecker = None,
        priority: PriorLevel = PriorLevel.MEAN,
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
        使用该装饰器，将方法标记为字符串结尾匹配的消息事件执行器。
        文本必须首先以 target 结尾，才能被进一步处理
        """
        end_matcher = EndMatch(target, logic_mode)

        def make_args(executor: AsyncFunc[None]) -> EventHandlerArgs:
            return EventHandlerArgs(
                executor=executor,
                type=MsgEventHandler,
                params=[
                    end_matcher,
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
    def on_regex_match(
        cls,
        target: str,
        checker: BotChecker = None,
        priority: PriorLevel = PriorLevel.MEAN,
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
        使用该装饰器，将方法标记为字符串正则匹配的消息事件执行器。
        文本必须包含指定的正则内容，才能被进一步处理
        """
        regex_matcher = RegexMatch(target)

        def make_args(executor: AsyncFunc[None]) -> EventHandlerArgs:
            return EventHandlerArgs(
                executor=executor,
                type=MsgEventHandler,
                params=[
                    regex_matcher,
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
    def on_request(
        cls,
        checker: BotChecker = None,
        priority: PriorLevel = PriorLevel.MEAN,
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
        使用该装饰器，将方法标记为请求事件执行器
        """

        def make_args(executor: AsyncFunc[None]) -> EventHandlerArgs:
            return EventHandlerArgs(
                executor=executor,
                type=ReqEventHandler,
                params=[
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
    def on_friend_request(
        cls,
        checker: BotChecker = None,
        priority: PriorLevel = PriorLevel.MEAN,
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
        使用该装饰器，将方法标记为私聊请求事件执行器
        """
        friend_checker = FriendReqChecker()
        if checker is not None:
            wrapped_checker = friend_checker & checker
        else:
            wrapped_checker = friend_checker

        def make_args(executor: AsyncFunc[None]) -> EventHandlerArgs:
            return EventHandlerArgs(
                executor=executor,
                type=ReqEventHandler,
                params=[
                    wrapped_checker,
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
    def on_group_request(
        cls,
        checker: BotChecker = None,
        priority: PriorLevel = PriorLevel.MEAN,
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
        使用该装饰器，将方法标记为群请求事件执行器
        """
        group_checker = GroupReqChecker()
        if checker is not None:
            wrapped_checker = group_checker & checker
        else:
            wrapped_checker = group_checker

        def make_args(executor: AsyncFunc[None]) -> EventHandlerArgs:
            return EventHandlerArgs(
                executor=executor,
                type=ReqEventHandler,
                params=[
                    wrapped_checker,
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
    def on_notice(
        cls,
        type: str = Literal[
            "group_upload",
            "group_admin",
            "group_decrease",
            "group_increase",
            "group_ban",
            "friend_add",
            "group_recall",
            "friend_recall",
            "group_card",
            "offline_file",
            "client_status",
            "essence",
            "notify",
            "honor",
            "poke",
            "lucky_king",
            "title",
            "ALL",
        ],
        checker: BotChecker = None,
        priority: PriorLevel = PriorLevel.MEAN,
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
        使用该装饰器，将方法标记为通知事件执行器
        """
        type_checker = NoticeTypeChecker(type)
        if checker is not None:
            wrapped_checker = type_checker & checker
        else:
            wrapped_checker = type_checker

        def make_args(executor: AsyncFunc[None]) -> EventHandlerArgs:
            return EventHandlerArgs(
                executor=executor,
                type=NoticeEventHandler,
                params=[
                    wrapped_checker,
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
    def on_meta_event(
        cls,
        checker: BotChecker = None,
        priority: PriorLevel = PriorLevel.MEAN,
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
        使用该装饰器，将方法标记为元事件执行器
        """

        def make_args(executor: AsyncFunc[None]) -> EventHandlerArgs:
            return EventHandlerArgs(
                executor=executor,
                type=MetaEventHandler,
                params=[
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
