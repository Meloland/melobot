import importlib.util
import inspect
import os
import pathlib
import sys
from asyncio import iscoroutinefunction
from pathlib import Path

from ..context.session import BotSessionManager
from ..types.abc import (
    BotHookRunnerArgs,
    EventHandlerArgs,
    LogicMode,
    PluginSignalHandlerArgs,
    ShareObjArgs,
    ShareObjCbArgs,
)
from ..types.exceptions import *
from ..types.typing import *
from ..utils.checker import (
    AtChecker,
    FriendReqChecker,
    GroupReqChecker,
    NoticeTypeChecker,
)
from ..utils.logger import PrefixLogger
from ..utils.matcher import ContainMatch, EndMatch, FullMatch, RegexMatch, StartMatch
from .handler import (
    AllEventHandler,
    EventHandler,
    MetaEventHandler,
    MsgEventHandler,
    NoticeEventHandler,
    ReqEventHandler,
)

if TYPE_CHECKING:
    from ..bot.hook import BotHookBus
    from ..types.abc import BotLife, SessionRule
    from ..utils.checker import BotChecker
    from ..utils.logger import BotLogger
    from ..utils.matcher import BotMatcher
    from ..utils.parser import BotParser
    from .ipc import PluginBus, PluginStore


class PluginProxy:
    """
    bot 插件代理类。供外部使用
    """

    def __init__(
        self,
        id: str,
        ver: str,
        path: Path,
        share_objs: list[tuple[str, str]],
        signal_methods: list[tuple[str, str]],
    ) -> None:
        self.id = id
        self.version = ver
        self.path = path
        self.shares = share_objs
        self.signal_methods = signal_methods


class PluginLoader:
    """
    插件加载器
    """

    @staticmethod
    def load_from_dir(plugin_path: str) -> tuple["Plugin", str]:
        """
        从指定插件目录加载插件
        """
        if not os.path.exists(os.path.join(plugin_path, "__init__.py")):
            raise PluginLoadError(
                f"{plugin_path} 缺乏入口主文件 __init__.py，插件无法加载"
            )
        plugin_name = os.path.basename(plugin_path)
        plugins_folder = str(pathlib.Path(plugin_path).parent.resolve(strict=True))
        plugins_folder_name = os.path.basename(plugins_folder)
        if plugins_folder not in sys.path:
            importlib.import_module(plugins_folder_name)
            sys.path.insert(0, plugins_folder)
        module = importlib.import_module(
            f"{plugins_folder_name}.{plugin_name}", f"{plugins_folder_name}"
        )

        plugin_class = None
        for obj in module.__dict__.values():
            if (
                isinstance(obj, type)
                and issubclass(obj, Plugin)
                and obj.__name__ != Plugin.__name__
            ):
                plugin_class = obj
                break
        if plugin_class is None:
            raise PluginLoadError(
                "指定的入口主文件中，未发现继承 Plugin 的插件类，无法加载插件"
            )
        plugin = plugin_class()
        file_path = inspect.getfile(module)
        return (plugin, file_path)

    @staticmethod
    def load_from_type(class_: Type["Plugin"]) -> tuple["Plugin", str]:
        """
        从插件类对象加载插件
        """
        plugin = class_()
        file_path = inspect.getfile(class_)
        return (plugin, file_path)

    @staticmethod
    def _build_plugin(
        plugin: "Plugin",
        root_path: Path,
        logger: "BotLogger",
        store: "PluginStore",
        plugin_bus: "PluginBus",
        bot_bus: "BotHookBus",
    ) -> None:
        plugin.PATH = root_path
        plugin.LOGGER = PrefixLogger(logger, plugin.ID)

        attrs_map = {
            k: v for k, v in inspect.getmembers(plugin) if not k.startswith("__")
        }
        share_objs_map = plugin._init_share_objs(store, attrs_map, plugin.SHARES)

        plugin._handlers = []
        signal_methods_map = []
        members = inspect.getmembers(plugin)
        for attr_name, val in members:
            if isinstance(val, EventHandlerArgs):
                handler = plugin._init_event_handler(
                    logger, val.executor, val.type, *val.params
                )
                plugin._handlers.append(handler)
            elif isinstance(val, BotHookRunnerArgs):
                plugin._init_hook_runner(bot_bus, val.func, val.type)
            elif isinstance(val, ShareObjCbArgs):
                plugin._init_share_obj_cb(store, val.namespace, val.id, val.cb)
            elif isinstance(val, PluginSignalHandlerArgs):
                plugin._init_plugin_signal_handler(
                    plugin_bus, val.namespace, val.signal, val.func
                )
                signal_methods_map.append((val.namespace, val.signal))

        plugin._proxy = PluginProxy(
            plugin.ID, plugin.VERSION, plugin.PATH, share_objs_map, signal_methods_map
        )

    @staticmethod
    def load(
        target: str | Type["Plugin"],
        logger: "BotLogger",
        store: "PluginStore",
        plugin_bus: "PluginBus",
        bot_bus: "BotHookBus",
    ) -> "Plugin":
        """
        加载插件
        """
        if isinstance(target, str):
            plugin, file_path = PluginLoader.load_from_dir(target)
        else:
            plugin, file_path = PluginLoader.load_from_type(target)
        root_path = pathlib.Path(file_path).parent.resolve(strict=True)
        PluginLoader._build_plugin(
            plugin, root_path, logger, store, plugin_bus, bot_bus
        )
        return plugin


class Plugin:
    """
    bot 插件基类。所有自定义插件必须继承该类实现。
    """

    def __init__(self) -> None:
        # 插件 id 和 version 标记
        self.ID: str = self.__class__.__name__
        # 插件版本标记
        self.VERSION: str = "1.0.0"
        # 插件类所在的文件路径，PosicPath 对象
        self.PATH: Path
        # 标记了该类有哪些实例属性需要被共享。元素是共享对象构造参数或字符串
        self.SHARES: List[ShareObjArgs | str] = []
        # 被二次包装的全局日志器
        self.LOGGER: PrefixLogger

        self._handlers: List[EventHandler]
        self._proxy: PluginProxy
        self._handlers: list[EventHandler]

    def _init_share_objs(
        self,
        store: "PluginStore",
        attrs_map: dict[str, Any],
        shares: List[ShareObjArgs | str],
    ) -> list[tuple[str, str]]:
        """
        初始化所有的共享对象。
        同时返回共享对象定义时，包含 (namespace, id) 元组的列表
        """
        share_objs = []
        for idx, val in enumerate(shares):
            if isinstance(val, str):
                shares[idx] = ShareObjArgs(val, self.ID, val)
        for share_obj in shares:
            property, namespace, id = (
                share_obj.property,
                share_obj.namespace,
                share_obj.id,
            )
            if property not in attrs_map.keys() and property is not None:
                raise PluginBuildError(
                    f"插件 {self.ID} 尝试共享一个不存在的属性 {property}"
                )
            store._create_so(property, namespace, id, self)
            share_objs.append((namespace, id))
        return share_objs

    def _init_event_handler(
        self,
        logger: "BotLogger",
        executor: Callable[[], Coroutine[Any, Any, None]],
        handler_class: Type[EventHandler],
        *params: Any,
    ) -> EventHandler:
        """
        初始化指定的 event handler，并返回
        """
        if not iscoroutinefunction(executor):
            raise PluginBuildError(f"事件处理器 {executor.__name__} 必须为异步方法")
        overtime_cb, conflict_cb = params[-1], params[-2]
        if overtime_cb and not callable(overtime_cb):
            raise PluginBuildError(
                f"超时回调方法 {overtime_cb.__name__} 必须为可调用对象"
            )
        if conflict_cb and not callable(conflict_cb):
            raise PluginBuildError(
                f"冲突回调方法 {conflict_cb.__name__} 必须为可调用对象"
            )
        handler = handler_class(executor, self, logger, *params)
        BotSessionManager.register(handler)
        return handler

    def _init_hook_runner(
        self,
        bot_bus: "BotHookBus",
        hook_func: Callable[..., Coroutine[Any, Any, None]],
        type: "BotLife",
    ) -> None:
        """
        初始化指定的 bot 生命周期的 hook 方法
        """
        if not iscoroutinefunction(hook_func):
            raise PluginBuildError(f"hook 方法 {hook_func.__name__} 必须为异步函数")
        bot_bus._register(type, hook_func, self)

    def _init_share_obj_cb(
        self,
        store: "PluginStore",
        namespace: str,
        id: str,
        cb: Callable[..., Coroutine[Any, Any, Any]],
    ) -> None:
        """
        初始化指定的共享对象的回调
        """
        if not iscoroutinefunction(cb):
            raise PluginBuildError(
                f"{namespace} 命名空间中，id 为 {id} 的共享对象，它的回调 {cb.__name__} 必须为异步函数"
            )
        store._bind_cb(namespace, id, cb, self)

    def _init_plugin_signal_handler(
        self,
        plugin_bus: "PluginBus",
        namespace: str,
        signal: str,
        func: Callable[..., Coroutine[Any, Any, Any]],
    ) -> None:
        """
        初始化指定的插件信号处理方法
        """
        if not iscoroutinefunction(func):
            raise PluginBuildError(f"插件信号处理方法 {func.__name__} 必须为异步函数")
        plugin_bus._register(namespace, signal, func, self)

    @classmethod
    def on_event(
        cls,
        checker: "BotChecker" = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: "SessionRule" = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Callable[[], Coroutine[Any, Any, None]] = None,
    ) -> Callable:
        """
        使用该装饰器，将方法标记为任意事件处理器（响应事件除外）
        """

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> EventHandlerArgs:
            return EventHandlerArgs(
                executor=executor,
                type=AllEventHandler,
                params=[
                    checker,
                    priority,
                    block,
                    temp,
                    session_rule,
                    session_hold,
                    direct_rouse,
                    conflict_wait,
                    conflict_cb,
                ],
            )

        return make_args

    @classmethod
    def on_message(
        cls,
        matcher: "BotMatcher" = None,
        parser: "BotParser" = None,
        checker: "BotChecker" = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: "SessionRule" = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Callable[[], Coroutine[Any, Any, None]] = None,
    ) -> Callable:
        """
        使用该装饰器，将方法标记为消息事件处理器
        """

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> EventHandlerArgs:
            return EventHandlerArgs(
                executor=executor,
                type=MsgEventHandler,
                params=[
                    matcher,
                    parser,
                    checker,
                    priority,
                    block,
                    temp,
                    session_rule,
                    session_hold,
                    direct_rouse,
                    conflict_wait,
                    conflict_cb,
                ],
            )

        return make_args

    @classmethod
    def on_every_message(
        cls,
        checker: "BotChecker" = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: "SessionRule" = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Callable[[], Coroutine[Any, Any, None]] = None,
    ) -> Callable:
        """
        使用该装饰器，将方法标记为任意消息事件处理器。
        任何消息经过校验后，不进行匹配和解析即可触发处理方法
        """

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> EventHandlerArgs:
            return EventHandlerArgs(
                executor=executor,
                type=MsgEventHandler,
                params=[
                    None,
                    None,
                    checker,
                    priority,
                    block,
                    temp,
                    session_rule,
                    session_hold,
                    direct_rouse,
                    conflict_wait,
                    conflict_cb,
                ],
            )

        return make_args

    @classmethod
    def on_at_qq(
        cls,
        qid: int = None,
        matcher: "BotMatcher" = None,
        parser: "BotParser" = None,
        checker: "BotChecker" = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: "SessionRule" = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Callable[[], Coroutine[Any, Any, None]] = None,
    ) -> Callable:
        """
        使用该装饰器，将方法标记为艾特消息匹配的消息事件处理器。
        必须首先是来自指定 qid 的艾特消息，才能被进一步处理
        """
        at_checker = AtChecker(qid)
        if checker is not None:
            wrapped_checker = at_checker & checker
        else:
            wrapped_checker = at_checker

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> EventHandlerArgs:
            return EventHandlerArgs(
                executor=executor,
                type=MsgEventHandler,
                params=[
                    matcher,
                    parser,
                    wrapped_checker,
                    priority,
                    block,
                    temp,
                    session_rule,
                    session_hold,
                    direct_rouse,
                    conflict_wait,
                    conflict_cb,
                ],
            )

        return make_args

    @classmethod
    def on_start_match(
        cls,
        target: str | list[str],
        logic_mode: LogicMode = LogicMode.OR,
        checker: "BotChecker" = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: "SessionRule" = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Callable[[], Coroutine[Any, Any, None]] = None,
    ) -> Callable:
        """
        使用该装饰器，将方法标记为字符串起始匹配的消息事件处理器。
        必须首先含有以 target 起始的文本，才能被进一步处理
        """
        start_matcher = StartMatch(target, logic_mode)

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> EventHandlerArgs:
            return EventHandlerArgs(
                executor=executor,
                type=MsgEventHandler,
                params=[
                    start_matcher,
                    None,
                    checker,
                    priority,
                    block,
                    temp,
                    session_rule,
                    session_hold,
                    direct_rouse,
                    conflict_wait,
                    conflict_cb,
                ],
            )

        return make_args

    @classmethod
    def on_contain_match(
        cls,
        target: str | list[str],
        logic_mode: LogicMode = LogicMode.OR,
        checker: "BotChecker" = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: "SessionRule" = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Callable[[], Coroutine[Any, Any, None]] = None,
    ) -> Callable:
        """
        使用该装饰器，将方法标记为字符串包含匹配的消息事件处理器。
        文本必须首先包含 target，才能被进一步处理
        """
        contain_matcher = ContainMatch(target, logic_mode)

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> EventHandlerArgs:
            return EventHandlerArgs(
                executor=executor,
                type=MsgEventHandler,
                params=[
                    contain_matcher,
                    None,
                    checker,
                    priority,
                    block,
                    temp,
                    session_rule,
                    session_hold,
                    direct_rouse,
                    conflict_wait,
                    conflict_cb,
                ],
            )

        return make_args

    @classmethod
    def on_full_match(
        cls,
        target: str | list[str],
        logic_mode: LogicMode = LogicMode.OR,
        checker: "BotChecker" = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: "SessionRule" = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Callable[[], Coroutine[Any, Any, None]] = None,
    ) -> Callable:
        """
        使用该装饰器，将方法标记为字符串相等匹配的消息事件处理器。
        文本必须首先与 target 内容完全一致，才能被进一步处理
        """
        full_matcher = FullMatch(target, logic_mode)

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> EventHandlerArgs:
            return EventHandlerArgs(
                executor=executor,
                type=MsgEventHandler,
                params=[
                    full_matcher,
                    None,
                    checker,
                    priority,
                    block,
                    temp,
                    session_rule,
                    session_hold,
                    direct_rouse,
                    conflict_wait,
                    conflict_cb,
                ],
            )

        return make_args

    @classmethod
    def on_end_match(
        cls,
        target: str | list[str],
        logic_mode: LogicMode = LogicMode.OR,
        checker: "BotChecker" = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: "SessionRule" = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Callable[[], Coroutine[Any, Any, None]] = None,
    ) -> Callable:
        """
        使用该装饰器，将方法标记为字符串结尾匹配的消息事件处理器。
        文本必须首先以 target 结尾，才能被进一步处理
        """
        end_matcher = EndMatch(target, logic_mode)

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> EventHandlerArgs:
            return EventHandlerArgs(
                executor=executor,
                type=MsgEventHandler,
                params=[
                    end_matcher,
                    None,
                    checker,
                    priority,
                    block,
                    temp,
                    session_rule,
                    session_hold,
                    direct_rouse,
                    conflict_wait,
                    conflict_cb,
                ],
            )

        return make_args

    @classmethod
    def on_regex_match(
        cls,
        target: str,
        checker: "BotChecker" = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: "SessionRule" = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Callable[[], Coroutine[Any, Any, None]] = None,
    ) -> Callable:
        """
        使用该装饰器，将方法标记为字符串正则匹配的消息事件处理器。
        文本必须包含指定的正则内容，才能被进一步处理
        """
        regex_matcher = RegexMatch(target)

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> EventHandlerArgs:
            return EventHandlerArgs(
                executor=executor,
                type=MsgEventHandler,
                params=[
                    regex_matcher,
                    None,
                    checker,
                    priority,
                    block,
                    temp,
                    session_rule,
                    session_hold,
                    direct_rouse,
                    conflict_wait,
                    conflict_cb,
                ],
            )

        return make_args

    @classmethod
    def on_request(
        cls,
        checker: "BotChecker" = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: "SessionRule" = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Callable[[], Coroutine[Any, Any, None]] = None,
    ) -> Callable:
        """
        使用该装饰器，将方法标记为请求事件处理器
        """

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> EventHandlerArgs:
            return EventHandlerArgs(
                executor=executor,
                type=ReqEventHandler,
                params=[
                    checker,
                    priority,
                    block,
                    temp,
                    session_rule,
                    session_hold,
                    direct_rouse,
                    conflict_wait,
                    conflict_cb,
                ],
            )

        return make_args

    @classmethod
    def on_friend_request(
        cls,
        checker: "BotChecker" = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: "SessionRule" = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Callable[[], Coroutine[Any, Any, None]] = None,
    ) -> Callable:
        """
        使用该装饰器，将方法标记为私聊请求事件处理器
        """
        friend_checker = FriendReqChecker()
        if checker is not None:
            wrapped_checker = friend_checker & checker
        else:
            wrapped_checker = friend_checker

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> EventHandlerArgs:
            return EventHandlerArgs(
                executor=executor,
                type=ReqEventHandler,
                params=[
                    wrapped_checker,
                    priority,
                    block,
                    temp,
                    session_rule,
                    session_hold,
                    direct_rouse,
                    conflict_wait,
                    conflict_cb,
                ],
            )

        return make_args

    @classmethod
    def on_group_request(
        cls,
        checker: "BotChecker" = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: "SessionRule" = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Callable[[], Coroutine[Any, Any, None]] = None,
    ) -> Callable:
        """
        使用该装饰器，将方法标记为群请求事件处理器
        """
        group_checker = GroupReqChecker()
        if checker is not None:
            wrapped_checker = group_checker & checker
        else:
            wrapped_checker = group_checker

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> EventHandlerArgs:
            return EventHandlerArgs(
                executor=executor,
                type=ReqEventHandler,
                params=[
                    wrapped_checker,
                    priority,
                    block,
                    temp,
                    session_rule,
                    session_hold,
                    direct_rouse,
                    conflict_wait,
                    conflict_cb,
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
        checker: "BotChecker" = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: "SessionRule" = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Callable[[], Coroutine[Any, Any, None]] = None,
    ) -> Callable:
        """
        使用该装饰器，将方法标记为通知事件处理器
        """
        type_checker = NoticeTypeChecker(type)
        if checker is not None:
            wrapped_checker = type_checker & checker
        else:
            wrapped_checker = type_checker

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> EventHandlerArgs:
            return EventHandlerArgs(
                executor=executor,
                type=NoticeEventHandler,
                params=[
                    wrapped_checker,
                    priority,
                    block,
                    temp,
                    session_rule,
                    session_hold,
                    direct_rouse,
                    conflict_wait,
                    conflict_cb,
                ],
            )

        return make_args

    @classmethod
    def on_meta_event(
        cls,
        checker: "BotChecker" = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: "SessionRule" = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Callable[[], Coroutine[Any, Any, None]] = None,
    ) -> Callable:
        """
        使用该装饰器，将方法标记为元事件处理器
        """

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> EventHandlerArgs:
            return EventHandlerArgs(
                executor=executor,
                type=MetaEventHandler,
                params=[
                    checker,
                    priority,
                    block,
                    temp,
                    session_rule,
                    session_hold,
                    direct_rouse,
                    conflict_wait,
                    conflict_cb,
                ],
            )

        return make_args
