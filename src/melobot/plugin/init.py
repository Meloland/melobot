import importlib.util
import os
import pathlib
import sys

from ..base.abc import (
    BotHookRunnerArgs,
    BotLife,
    EventHandlerArgs,
    LogicMode,
    PluginSignalHandlerArgs,
    ShareObjArgs,
    ShareObjCbArgs,
)
from ..base.exceptions import PluginInitError
from ..base.tools import to_async
from ..base.typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Literal,
    Optional,
    P,
    PriorLevel,
    Union,
)
from ..utils.checker import (
    AtChecker,
    FriendReqChecker,
    GroupReqChecker,
    NoticeTypeChecker,
)
from ..utils.matcher import ContainMatch, EndMatch, FullMatch, RegexMatch, StartMatch
from .handler import (
    AllEventHandler,
    MetaEventHandler,
    MsgEventHandler,
    NoticeEventHandler,
    ReqEventHandler,
)

if TYPE_CHECKING:
    from ..base.abc import SessionRule, WrappedChecker
    from ..utils.checker import BotChecker
    from ..utils.matcher import BotMatcher
    from ..utils.parser import BotParser


class PluginProxy:
    """Bot 插件代理类。供外部使用."""

    def __init__(
        self,
        id: str,
        ver: str,
        desc: str,
        doc: str,
        keywords: list[str],
        url: str,
        share_objs: list[tuple[str, str]],
        share_cbs: list[tuple[str, str]],
        signal_methods: list[tuple[str, str]],
    ) -> None:
        self.id = id
        self.version = ver
        self.desc = desc
        self.doc = doc
        self.keywords = keywords
        self.url = url
        self.shares = share_objs
        self.share_cbs = share_cbs
        self.signal_methods = signal_methods


class PluginLoader:
    """插件加载器."""

    @staticmethod
    def load_from_dir(plugin_path: str) -> "BotPlugin":
        """从指定插件目录加载插件."""
        if not os.path.exists(os.path.join(plugin_path, "__init__.py")):
            raise PluginInitError(
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

        plugin = None
        for obj in module.__dict__.values():
            if isinstance(obj, BotPlugin):
                plugin = obj
                break
        if plugin is None:
            raise PluginInitError("指定的入口主文件中，未发现 Plugin 实例，无效导入")
        return plugin

    @staticmethod
    def load(target: Union[str, "BotPlugin"]) -> "BotPlugin":
        """加载插件."""
        if isinstance(target, str):
            plugin = PluginLoader.load_from_dir(target)
        else:
            plugin = target
        plugin._self_build()
        return plugin


class BotPlugin:
    """Bot 插件基类。所有自定义插件必须继承该类实现。"""

    def __init__(
        self,
        id: str,
        version: str,
        desc: str = "",
        doc: str = "",
        keywords: Optional[list[str]] = None,
        url: str = "",
    ) -> None:
        self.__id__ = id
        self.__version__ = version
        self.__desc__ = desc
        self.__keywords__ = keywords if keywords is not None else []
        self.__url__ = url
        self.__pdoc__ = doc

        self.__handler_args__: list[EventHandlerArgs] = []
        self.__signal_args__: list[PluginSignalHandlerArgs] = []
        self.__share_args__: list[ShareObjArgs] = []
        self.__share_cb_args__: list[ShareObjCbArgs] = []
        self.__hook_args__: list[BotHookRunnerArgs] = []

        self.__proxy__: PluginProxy

    def _self_build(self) -> None:
        self.__proxy__ = PluginProxy(
            self.__id__,
            self.__version__,
            self.__desc__,
            self.__pdoc__,
            self.__keywords__,
            self.__url__,
            [(args.namespace, args.id) for args in self.__share_args__],
            [(args.namespace, args.id) for args in self.__share_cb_args__],
            [(args.namespace, args.signal) for args in self.__signal_args__],
        )
        check_pass = all(
            False
            for pair in self.__proxy__.share_cbs
            if pair not in self.__proxy__.shares
        )
        if not check_pass:
            raise PluginInitError(
                f"插件 {self.__id__} 不能为不属于自己的共享对象注册回调"
            )

    def on_signal(self, namespace: str, signal: str):
        def make_args(
            func: Callable[P, Coroutine[Any, Any, Any]]
        ) -> Callable[P, Coroutine[Any, Any, Any]]:
            self.__signal_args__.append(
                PluginSignalHandlerArgs(func, namespace, signal)
            )
            return func

        return make_args

    def on_share(
        self, namespace: str, id: str, reflector: Optional[Callable[[], Any]] = None
    ):
        if reflector is not None:
            self.__share_args__.append(ShareObjArgs(namespace, id, to_async(reflector)))
            return

        def make_args(
            func: Callable[[], Coroutine[Any, Any, Any]]
        ) -> Callable[[], Coroutine[Any, Any, Any]]:
            self.__share_args__.append(ShareObjArgs(namespace, id, func))
            return func

        return make_args

    def on_share_affected(self, namespace: str, id: str):
        def make_args(
            func: Callable[P, Coroutine[Any, Any, Any]]
        ) -> Callable[P, Coroutine[Any, Any, Any]]:
            self.__share_cb_args__.append(ShareObjCbArgs(namespace, id, func))
            return func

        return make_args

    def on_bot_life(self, type: BotLife):
        def make_args(
            func: Callable[P, Coroutine[Any, Any, None]]
        ) -> Callable[P, Coroutine[Any, Any, None]]:
            self.__hook_args__.append(BotHookRunnerArgs(func, type))
            return func

        return make_args

    @property
    def on_plugins_loaded(self):
        return self.on_bot_life(BotLife.LOADED)

    @property
    def on_connected(self):
        return self.on_bot_life(BotLife.CONNECTED)

    @property
    def on_before_close(self):
        return self.on_bot_life(BotLife.BEFORE_CLOSE)

    @property
    def on_before_stop(self):
        return self.on_bot_life(BotLife.BEFORE_STOP)

    @property
    def on_event_built(self):
        return self.on_bot_life(BotLife.EVENT_BUILT)

    @property
    def on_action_presend(self):
        return self.on_bot_life(BotLife.ACTION_PRESEND)

    def on_event(
        self,
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ):
        """使用该装饰器，将方法标记为任意事件处理器（响应事件除外）"""

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> Callable[[], Coroutine[Any, Any, None]]:
            self.__handler_args__.append(
                EventHandlerArgs(
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
            )
            return executor

        return make_args

    def on_message(
        self,
        matcher: Optional["BotMatcher"] = None,
        parser: Optional["BotParser"] = None,
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ):
        """使用该装饰器，将方法标记为消息事件处理器."""

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> Callable[[], Coroutine[Any, Any, None]]:
            self.__handler_args__.append(
                EventHandlerArgs(
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
            )
            return executor

        return make_args

    def on_every_message(
        self,
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ):
        """使用该装饰器，将方法标记为任意消息事件处理器。 任何消息经过校验后，不进行匹配和解析即可触发处理方法."""

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> Callable[[], Coroutine[Any, Any, None]]:
            self.__handler_args__.append(
                EventHandlerArgs(
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
            )
            return executor

        return make_args

    def on_at_qq(
        self,
        qid: Optional[int] = None,
        matcher: Optional["BotMatcher"] = None,
        parser: Optional["BotParser"] = None,
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ):
        """使用该装饰器，将方法标记为艾特消息匹配的消息事件处理器。 必须首先是来自指定 qid 的艾特消息，才能被进一步处理."""
        at_checker = AtChecker(qid)
        wrapped_checker: AtChecker | "WrappedChecker"
        if checker is not None:
            wrapped_checker = at_checker & checker
        else:
            wrapped_checker = at_checker

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> Callable[[], Coroutine[Any, Any, None]]:
            self.__handler_args__.append(
                EventHandlerArgs(
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
            )
            return executor

        return make_args

    def on_start_match(
        self,
        target: str | list[str],
        logic_mode: LogicMode = LogicMode.OR,
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ):
        """使用该装饰器，将方法标记为字符串起始匹配的消息事件处理器。 必须首先含有以 target 起始的文本，才能被进一步处理."""
        start_matcher = StartMatch(target, logic_mode)

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> Callable[[], Coroutine[Any, Any, None]]:
            self.__handler_args__.append(
                EventHandlerArgs(
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
            )
            return executor

        return make_args

    def on_contain_match(
        self,
        target: str | list[str],
        logic_mode: LogicMode = LogicMode.OR,
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ):
        """使用该装饰器，将方法标记为字符串包含匹配的消息事件处理器。 文本必须首先包含 target，才能被进一步处理."""
        contain_matcher = ContainMatch(target, logic_mode)

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> Callable[[], Coroutine[Any, Any, None]]:
            self.__handler_args__.append(
                EventHandlerArgs(
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
            )
            return executor

        return make_args

    def on_full_match(
        self,
        target: str | list[str],
        logic_mode: LogicMode = LogicMode.OR,
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ):
        """使用该装饰器，将方法标记为字符串相等匹配的消息事件处理器。 文本必须首先与 target 内容完全一致，才能被进一步处理."""
        full_matcher = FullMatch(target, logic_mode)

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> Callable[[], Coroutine[Any, Any, None]]:
            self.__handler_args__.append(
                EventHandlerArgs(
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
            )
            return executor

        return make_args

    def on_end_match(
        self,
        target: str | list[str],
        logic_mode: LogicMode = LogicMode.OR,
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ):
        """使用该装饰器，将方法标记为字符串结尾匹配的消息事件处理器。 文本必须首先以 target 结尾，才能被进一步处理."""
        end_matcher = EndMatch(target, logic_mode)

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> Callable[[], Coroutine[Any, Any, None]]:
            self.__handler_args__.append(
                EventHandlerArgs(
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
            )
            return executor

        return make_args

    def on_regex_match(
        self,
        target: str,
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ):
        """使用该装饰器，将方法标记为字符串正则匹配的消息事件处理器。 文本必须包含指定的正则内容，才能被进一步处理."""
        regex_matcher = RegexMatch(target)

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> Callable[[], Coroutine[Any, Any, None]]:
            self.__handler_args__.append(
                EventHandlerArgs(
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
            )
            return executor

        return make_args

    def on_request(
        self,
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ):
        """使用该装饰器，将方法标记为请求事件处理器."""

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> Callable[[], Coroutine[Any, Any, None]]:
            self.__handler_args__.append(
                EventHandlerArgs(
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
            )
            return executor

        return make_args

    def on_friend_request(
        self,
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ):
        """使用该装饰器，将方法标记为私聊请求事件处理器."""
        friend_checker = FriendReqChecker()
        wrapped_checker: FriendReqChecker | "WrappedChecker"
        if checker is not None:
            wrapped_checker = friend_checker & checker
        else:
            wrapped_checker = friend_checker

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> Callable[[], Coroutine[Any, Any, None]]:
            self.__handler_args__.append(
                EventHandlerArgs(
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
            )
            return executor

        return make_args

    def on_group_request(
        self,
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ):
        """使用该装饰器，将方法标记为群请求事件处理器."""
        group_checker = GroupReqChecker()
        wrapped_checker: GroupReqChecker | "WrappedChecker"
        if checker is not None:
            wrapped_checker = group_checker & checker
        else:
            wrapped_checker = group_checker

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> Callable[[], Coroutine[Any, Any, None]]:
            self.__handler_args__.append(
                EventHandlerArgs(
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
            )
            return executor

        return make_args

    def on_notice(
        self,
        type: Literal[
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
        ] = "ALL",
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ):
        """使用该装饰器，将方法标记为通知事件处理器."""
        type_checker = NoticeTypeChecker(type)
        wrapped_checker: NoticeTypeChecker | "WrappedChecker"
        if checker is not None:
            wrapped_checker = type_checker & checker
        else:
            wrapped_checker = type_checker

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> Callable[[], Coroutine[Any, Any, None]]:
            self.__handler_args__.append(
                EventHandlerArgs(
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
            )
            return executor

        return make_args

    def on_meta_event(
        self,
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ):
        """使用该装饰器，将方法标记为元事件处理器."""

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> Callable[[], Coroutine[Any, Any, None]]:
            self.__handler_args__.append(
                EventHandlerArgs(
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
            )
            return executor

        return make_args
