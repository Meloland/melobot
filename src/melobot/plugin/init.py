import importlib.util
import os
import pathlib
import sys

from ..base.abc import (
    BotEvent,
    BotHookRunnerArgs,
    BotLife,
    CustomChecker,
    EventHandlerArgs,
    PluginSignalHandlerArgs,
    ShareObjArgs,
    ShareObjCbArgs,
)
from ..base.exceptions import BotPluginError
from ..base.ioc import DependManager
from ..base.tools import to_async
from ..base.typing import (
    TYPE_CHECKING,
    Any,
    AsyncCallable,
    Callable,
    LogicMode,
    Optional,
    P,
    PriorLevel,
    T,
    Union,
)
from ..context.session import SessionOption
from ..meta import ReadOnly
from ..models import MessageEvent, MetaEvent, NoticeEvent, RequestEvent
from ..utils.checker import AtMsgChecker, BotChecker
from ..utils.matcher import (
    ContainMatcher,
    EndMatcher,
    FullMatcher,
    RegexMatcher,
    StartMatcher,
)
from ..utils.parser import CmdArgFormatter, CmdParser
from .handler import (
    AllEventHandler,
    EventHandler,
    MetaEventHandler,
    MsgEventHandler,
    NoticeEventHandler,
    ReqEventHandler,
)

if TYPE_CHECKING:
    from ..utils.matcher import BotMatcher
    from ..utils.parser import BotParser


class PluginProxy(metaclass=ReadOnly):
    """Bot 插件代理类

    通过 bot 实例获取插件时，将获取此对象的列表

    .. admonition:: 提示
       :class: tip

       一般无需手动实例化该类，多数情况会直接使用本类对象，或将本类用作类型注解。
    """

    def __init__(
        self,
        id: str,
        ver: str,
        desc: str,
        doc: str,
        keywords: list[str],
        url: str,
        multi_use: bool,
        share_objs: list[tuple[str, str]],
        share_cbs: list[tuple[str, str]],
        signal_methods: list[tuple[str, str]],
    ) -> None:
        #: 插件的 id
        self.id: str = id
        #: 插件的版本
        self.version: str = ver
        #: 插件的简短描述
        self.desc: str = desc
        #: 插件的长篇描述
        self.doc: str = doc
        #: 插件的关键词
        self.keywords: list[str] = keywords
        #: 插件的项目地址
        self.url: str = url
        #: 是否支持同时被多个 bot 实例加载
        self.multi_use = multi_use
        #: 插件的共享对象标识：[(命名空间，id), ...]
        self.shares: list[tuple[str, str]] = share_objs
        #: 插件的共享对象回调标识：[(命名空间，id), ...]
        self.share_cbs: list[tuple[str, str]] = share_cbs
        #: 插件的信号处理方法标识：[(命名空间, 信号名), ...]
        self.signal_methods: list[tuple[str, str]] = signal_methods


class PluginLoader:
    """插件加载器"""

    @staticmethod
    def load_from_dir(plugin_path: str) -> "BotPlugin":
        """从指定插件目录加载插件"""
        if not os.path.exists(os.path.join(plugin_path, "__init__.py")):
            raise BotPluginError(
                f"{plugin_path} 缺乏入口主文件 __init__.py，插件无法加载"
            )

        p_name = os.path.basename(plugin_path)
        p_folder = str(pathlib.Path(plugin_path).parent.resolve(strict=True))
        p_folder_name = os.path.basename(p_folder)

        if p_folder not in sys.path:
            importlib.import_module(p_folder_name)
            sys.path.insert(0, p_folder)

        module = importlib.import_module(f"{p_folder_name}.{p_name}", f"{p_folder_name}")

        for obj in module.__dict__.values():
            if isinstance(obj, BotPlugin):
                plugin = obj
                break
        else:
            raise BotPluginError("指定的入口主文件中，未发现 Plugin 实例，无效导入")

        return plugin

    @staticmethod
    def load(target: Union[str, "BotPlugin"]) -> "BotPlugin":
        """加载插件"""
        if isinstance(target, str):
            plugin = PluginLoader.load_from_dir(target)
        else:
            plugin = target

        plugin._self_build()
        return plugin


class BotPlugin:
    """插件类，使用该类实例化一个插件"""

    def __init__(
        self,
        id: str,
        version: str,
        desc: str = "",
        doc: str = "",
        keywords: Optional[list[str]] = None,
        url: str = "",
        multi_use: bool = False,
    ) -> None:
        """初始化一个插件

        :param id: 插件的 id
        :param version: 插件的版本
        :param desc: 插件功能描述
        :param doc: 插件简单的文档说明
        :param keywords: 关键词列表
        :param url: 插件项目地址
        :param multi_use: 是否支持同时被多个 bot 实例加载
        """
        #: 本实例属性与初始化参数一一对应
        self.ID = id
        #: 本实例属性与初始化参数一一对应
        self.VER = version
        #: 本实例属性与初始化参数一一对应
        self.DESC = desc
        #: 本实例属性与初始化参数一一对应
        self.KEYWORDS = keywords if keywords is not None else []
        #: 本实例属性与初始化参数一一对应
        self.URL = url
        #: 本实例属性与初始化参数一一对应
        self.DOC = doc
        #: 本实例属性与初始化参数一一对应
        self.MULTI_USE = multi_use

        self._loaded_once = False
        self.__handler_args__: list[EventHandlerArgs] = []
        self.__signal_args__: list[PluginSignalHandlerArgs] = []
        self.__share_args__: list[ShareObjArgs] = []
        self.__share_cb_args__: list[ShareObjCbArgs] = []
        self.__hook_args__: list[BotHookRunnerArgs] = []
        self.__proxy__: PluginProxy

    def _self_build(self) -> None:
        self.__proxy__ = PluginProxy(
            self.ID,
            self.VER,
            self.DESC,
            self.DOC,
            self.KEYWORDS,
            self.URL,
            self.MULTI_USE,
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
            raise BotPluginError(f"插件 {self.ID} 不能为不属于自己的共享对象绑定回调")

    def _on_event(
        self, handler_type: type[EventHandler], params: list[Any]
    ) -> Callable[[AsyncCallable[P, None]], AsyncCallable[P, None]]:

        def save_args(executor: AsyncCallable[P, None]) -> AsyncCallable[P, None]:
            self.__handler_args__.append(
                EventHandlerArgs(
                    executor=DependManager.inject(executor),
                    type=handler_type,
                    params=params,
                )
            )
            return executor

        return save_args

    def on_event(
        self,
        checker: Optional[BotChecker] | Callable[[BotEvent], bool] | None = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        option: Optional[SessionOption] = None,
    ):
        """绑定一个任意事件处理方法

        :param checker: 使用的检查器，为空则默认通过检查
        :param priority: 优先级
        :param block: 是否进行优先级阻断
        :param temp: 是否是一次性的
        :param option: 会话选项（用于指定会话的工作方式）
        """
        if checker is not None:
            checker = checker if isinstance(checker, BotChecker) else CustomChecker(checker)
        return self._on_event(
            AllEventHandler,
            params=[checker, priority, block, temp, option],
        )

    def on_message(
        self,
        matcher: Optional["BotMatcher"] = None,
        parser: Optional["BotParser"] = None,
        checker: BotChecker[MessageEvent] | Callable[[MessageEvent], bool] | None = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        option: Optional[SessionOption[MessageEvent]] = None,
    ):
        """绑定一个消息事件处理方法

        :param matcher: 使用的匹配器（和解析器二选一）
        :param parser: 使用的解析器（和匹配器二选一）
        :param checker: 使用的检查器，为空则默认通过检查
        :param priority: 优先级
        :param block: 是否进行优先级阻断
        :param temp: 是否是一次性的
        :param option: 会话选项（用于指定会话的工作方式）
        """
        if checker is not None:
            checker = checker if isinstance(checker, BotChecker) else CustomChecker(checker)
        return self._on_event(
            MsgEventHandler,
            params=[matcher, parser, checker, priority, block, temp, option],
        )

    def on_at_qq(
        self,
        qid: Optional[int] = None,
        matcher: Optional["BotMatcher"] = None,
        parser: Optional["BotParser"] = None,
        checker: BotChecker[MessageEvent] | Callable[[MessageEvent], bool] | None = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        option: Optional[SessionOption[MessageEvent]] = None,
    ):
        """绑定一个艾特消息事件处理方法

        消息必须是艾特消息，且匹配成功才能被进一步处理。

        :param qid: 被艾特的 qq 号。为空则接受所有艾特消息;不为空则只接受指定 qid 被艾特的艾特消息
        :param matcher: 使用的匹配器（和解析器二选一）
        :param parser: 使用的解析器（和匹配器二选一）
        :param checker: 使用的检查器，为空则默认通过检查
        :param priority: 优先级
        :param block: 是否进行优先级阻断
        :param temp: 是否是一次性的
        :param option: 会话选项（用于指定会话的工作方式）
        """
        if checker is not None:
            checker = checker if isinstance(checker, BotChecker) else CustomChecker(checker)
        checker = AtMsgChecker(qid) if checker is None else AtMsgChecker(qid) & checker
        return self.on_message(matcher, parser, checker, priority, block, temp, option)

    def on_command(
        self,
        cmd_start: str | list[str],
        cmd_sep: str | list[str],
        targets: str | list[str],
        formatters: Optional[list[CmdArgFormatter | None]] = None,
        checker: BotChecker[MessageEvent] | Callable[[MessageEvent], bool] | None = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        option: Optional[SessionOption[MessageEvent]] = None,
    ):
        """绑定一个消息事件处理方法

        .. admonition:: 注意
           :class: caution

           - 命令起始符和命令间隔符不允许包含：引号，各种括号，反斜杠，数字，英文，控制字符及各类空白字符。
           - 命令起始符不能是命令间隔符的子序列，反之亦然。

        :param cmd_start: 命令起始符（可以是字符串或字符串列表）
        :param cmd_sep: 命令间隔符（可以是字符串或字符串列表）
        :param targets: 匹配的命令名
        :param formatters: 格式化器列表（列表可以包含空值，即此位置的参数无格式化）
        :param checker: 使用的检查器，为空则默认通过检查
        :param priority: 优先级
        :param block: 是否进行优先级阻断
        :param temp: 是否是一次性的
        :param option: 会话选项（用于指定会话的工作方式）
        """
        if checker is not None:
            checker = checker if isinstance(checker, BotChecker) else CustomChecker(checker)
        parser = CmdParser(cmd_start, cmd_sep, targets, formatters)
        return self.on_message(None, parser, checker, priority, block, temp, option)

    def on_start_match(
        self,
        target: str | list[str],
        logic_mode: LogicMode = LogicMode.OR,
        checker: BotChecker[MessageEvent] | Callable[[MessageEvent], bool] | None = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        option: Optional[SessionOption[MessageEvent]] = None,
    ):
        """绑定一个字符串起始匹配的消息事件处理方法

        `target` 为字符串时，只进行一次起始匹配，即判断是否匹配成功。
        `target` 为字符串列表时，所有字符串都进行起始匹配，再将所有结果使用给定
        `logic_mode` 计算是否匹配成功。

        消息必须匹配成功才能被进一步处理。

        :param target: 匹配目标
        :param logic_mode: `target` 为 `list[str]` 时的计算模式
        :param checker: 使用的检查器，为空则默认通过检查
        :param priority: 优先级
        :param block: 是否进行优先级阻断
        :param temp: 是否是一次性的
        :param option: 会话选项（用于指定会话的工作方式）
        """
        if checker is not None:
            checker = checker if isinstance(checker, BotChecker) else CustomChecker(checker)
        return self.on_message(
            StartMatcher(target, logic_mode), None, checker, priority, block, temp, option
        )

    def on_contain_match(
        self,
        target: str | list[str],
        logic_mode: LogicMode = LogicMode.OR,
        checker: BotChecker[MessageEvent] | Callable[[MessageEvent], bool] | None = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        option: Optional[SessionOption[MessageEvent]] = None,
    ):
        """绑定一个字符串包含匹配的消息事件处理方法

        `target` 为字符串时，只进行一次包含匹配，即判断是否匹配成功。
        `target` 为字符串列表时，所有字符串都进行包含匹配，再将所有结果使用给定
        `logic_mode` 计算是否匹配成功。

        消息必须匹配成功才能被进一步处理。

        :param target: 匹配目标
        :param logic_mode: `target` 为 `list[str]` 时的计算模式
        :param checker: 使用的检查器，为空则默认通过检查
        :param priority: 优先级
        :param block: 是否进行优先级阻断
        :param temp: 是否是一次性的
        :param option: 会话选项（用于指定会话的工作方式）
        """
        if checker is not None:
            checker = checker if isinstance(checker, BotChecker) else CustomChecker(checker)
        matcher = ContainMatcher(target, logic_mode)
        return self.on_message(matcher, None, checker, priority, block, temp, option)

    def on_full_match(
        self,
        target: str | list[str],
        logic_mode: LogicMode = LogicMode.OR,
        checker: BotChecker[MessageEvent] | Callable[[MessageEvent], bool] | None = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        option: Optional[SessionOption[MessageEvent]] = None,
    ):
        """绑定一个字符串全匹配的消息事件处理方法

        `target` 为字符串时，只进行一次全匹配，即判断是否匹配成功。
        `target` 为字符串列表时，所有字符串都进行全匹配，再将所有结果使用给定
        `logic_mode` 计算是否匹配成功。

        消息必须匹配成功才能被进一步处理。

        :param target: 匹配目标
        :param logic_mode: `target` 为 `list[str]` 时的计算模式
        :param checker: 使用的检查器，为空则默认通过检查
        :param priority: 优先级
        :param block: 是否进行优先级阻断
        :param temp: 是否是一次性的
        :param option: 会话选项（用于指定会话的工作方式）
        """
        if checker is not None:
            checker = checker if isinstance(checker, BotChecker) else CustomChecker(checker)
        return self.on_message(
            FullMatcher(target, logic_mode), None, checker, priority, block, temp, option
        )

    def on_end_match(
        self,
        target: str | list[str],
        logic_mode: LogicMode = LogicMode.OR,
        checker: BotChecker[MessageEvent] | Callable[[MessageEvent], bool] | None = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        option: Optional[SessionOption[MessageEvent]] = None,
    ):
        """绑定一个字符串结尾匹配的消息事件处理方法

        `target` 为字符串时，只进行一次结尾匹配，即判断是否匹配成功。
        `target` 为字符串列表时，所有字符串都进行结尾匹配，再将所有结果使用给定
        `logic_mode` 计算是否匹配成功。

        消息必须匹配成功才能被进一步处理。

        :param target: 匹配目标
        :param logic_mode: `target` 为 `list[str]` 时的计算模式
        :param checker: 使用的检查器，为空则默认通过检查
        :param priority: 优先级
        :param block: 是否进行优先级阻断
        :param temp: 是否是一次性的
        :param option: 会话选项（用于指定会话的工作方式）
        """
        if checker is not None:
            checker = checker if isinstance(checker, BotChecker) else CustomChecker(checker)
        return self.on_message(
            EndMatcher(target, logic_mode), None, checker, priority, block, temp, option
        )

    def on_regex_match(
        self,
        target: str,
        checker: BotChecker[MessageEvent] | Callable[[MessageEvent], bool] | None = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        option: Optional[SessionOption[MessageEvent]] = None,
    ):
        """绑定一个字符串正则匹配的消息事件处理方法

        消息必须匹配成功才能被进一步处理。

        :param target: 匹配目标的正则表达式，在匹配时，它应该可以使 :meth:`re.findall` 不返回空列表
        :param checker: 使用的检查器，为空则默认通过检查
        :param priority: 优先级
        :param block: 是否进行优先级阻断
        :param temp: 是否是一次性的
        :param option: 会话选项（用于指定会话的工作方式）
        """
        if checker is not None:
            checker = checker if isinstance(checker, BotChecker) else CustomChecker(checker)
        return self.on_message(
            RegexMatcher(target), None, checker, priority, block, temp, option
        )

    def on_request(
        self,
        checker: BotChecker[RequestEvent] | Callable[[RequestEvent], bool] | None = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        option: Optional[SessionOption[RequestEvent]] = None,
    ):
        """绑定一个请求事件处理方法

        :param checker: 使用的检查器，为空则默认通过检查
        :param priority: 优先级
        :param block: 是否进行优先级阻断
        :param temp: 是否是一次性的
        :param option: 会话选项（用于指定会话的工作方式）
        """
        if checker is not None:
            checker = checker if isinstance(checker, BotChecker) else CustomChecker(checker)
        return self._on_event(
            ReqEventHandler,
            params=[checker, priority, block, temp, option],
        )

    def on_notice(
        self,
        checker: BotChecker[NoticeEvent] | Callable[[NoticeEvent], bool] | None = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        option: Optional[SessionOption[NoticeEvent]] = None,
    ):
        """绑定一个通知事件处理方法

        :param type: 通知的类型，为 "ALL" 时接受所有通知
        :param checker: 使用的检查器，为空则默认通过检查
        :param priority: 优先级
        :param block: 是否进行优先级阻断
        :param temp: 是否是一次性的
        :param option: 会话选项（用于指定会话的工作方式）
        """
        if checker is not None:
            checker = checker if isinstance(checker, BotChecker) else CustomChecker(checker)
        return self._on_event(
            NoticeEventHandler,
            params=[checker, priority, block, temp, option],
        )

    def on_meta_event(
        self,
        checker: BotChecker[MetaEvent] | Callable[[MetaEvent], bool] | None = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        option: Optional[SessionOption[MetaEvent]] = None,
    ):
        """绑定一个元事件处理方法

        :param checker: 使用的检查器，为空则默认通过检查
        :param priority: 优先级
        :param block: 是否进行优先级阻断
        :param temp: 是否是一次性的
        :param option: 会话选项（用于指定会话的工作方式）
        """
        if checker is not None:
            checker = checker if isinstance(checker, BotChecker) else CustomChecker(checker)
        return self._on_event(
            MetaEventHandler,
            params=[checker, priority, block, temp, option],
        )

    def on_signal(self, signal: str, namespace: Optional[str] = None):
        """绑定一个信号处理方法

        `namespace` 为空时，自动设置它为当前插件的 :attr:`~.BotPlugin.ID`

        本方法作为异步函数的装饰器使用，此时可绑定一个函数为信号处理方法。

        .. code:: python

           # 假设存在一个名为 plugin 的变量，是 BotPlugin 实例
           # 为在命名空间 BaseUtils 中，名为 txt2img 的信号绑定处理方法：
           @plugin.on_signal("txt2img", "BaseUtils")
           async def get_img_of_txt(text: str, format: Any) -> bytes:
               # melobot 对被装饰函数的参数类型和返回值没有限制
               # 接下来是具体逻辑
               ...
           # 在这个示例中，具体的功能是为其他插件提供转换大段文本为图片的能力，因为大段文本不便于发送

        .. admonition:: 注意
           :class: caution

           在一个 bot 实例的范围内，同命名空间同名称的信号，只能绑定一个处理方法。

        :param namespace: 信号的命名空间
        :param signal: 信号的名称
        """

        def make_args(func: AsyncCallable[P, T]) -> AsyncCallable[P, T]:
            self.__signal_args__.append(
                PluginSignalHandlerArgs(
                    DependManager.inject(func),
                    namespace if namespace is not None else self.ID,
                    signal,
                )
            )
            return func

        return make_args

    def on_share(
        self,
        id: str,
        namespace: Optional[str] = None,
        reflector: Optional[Callable[P, Any]] = None,
    ):
        """注册一个共享对象，同时绑定它的值获取方法

        `namespace` 为空时，自动设置它为当前插件的 :attr:`~.BotPlugin.ID`

        本方法可作为异步函数的装饰器使用，此时被装饰函数就是共享对象的值获取方法：

        .. code:: python

           # 假设存在一个名为 plugin 的变量，是 BotPlugin 实例
           # 在命名空间 HelpUtils 中，注册一个名为 all_helps 的共享对象，且绑定值获取方法：
           @plugin.on_share("all_helps", "HelpUtils")
           async def get_all_helps() -> str:
               # melobot 对被装饰函数的要求：无参数，但必须有返回值
               return ALL_HELPS_INFO_STR
           # 在这个示例中，具体的功能是在插件间共享 “所有插件的帮助文本” 这一数据

        当然，值获取方法较为简单时，直接传参即可：

        .. code:: python

           # 最后一个参数不能给定具体的值，必须为一个同步函数
           plugin.on_share("all_helps", "HelpUtils", lambda: ALL_HELPS_INFO_STR)

        .. admonition:: 注意
           :class: caution

           在一个 bot 实例的范围内，同命名空间同名称的共享对象，只能注册一个。

        :param namespace: 共享对象的命名空间
        :param id: 共享对象的 id 标识
        :param reflector: 本方法当作异步函数的装饰器使用时，本参数为空；直接使用本方法时，参数为共享对象值获取的同步函数
        """
        _namespace = namespace if namespace is not None else self.ID
        if reflector is not None:
            self.__share_args__.append(
                ShareObjArgs(DependManager.inject(to_async(reflector)), _namespace, id)
            )
            return

        def make_args(func: AsyncCallable[P, T]) -> AsyncCallable[P, T]:
            self.__share_args__.append(
                ShareObjArgs(DependManager.inject(func), _namespace, id)
            )
            return func

        return make_args

    def on_share_affected(self, id: str, namespace: Optional[str] = None):
        """为一个共享对象绑定回调方法

        `namespace` 为空时，自动设置它为当前插件的 :attr:`~.BotPlugin.ID`

        本方法作为异步函数的装饰器使用，此时可为一个共享对象绑定回调方法。

        .. code:: python

           # 假设存在一个名为 plugin 的变量，是 BotPlugin 实例
           # 为在命名空间 HelpUtils 中，名为 all_helps 的共享对象绑定回调方法：
           @plugin.on_share_affected("all_helps", "HelpUtils")
           async def add_a_help(text: str) -> bool:
               # melobot 对被装饰函数的参数类型和返回值没有限制
               # 接下来是具体逻辑
               ...
           # 此回调用于被其他插件触发，为它们提供“影响”共享对象的能力，
           # 在这个示例中，具体的功能是让其他插件可以添加一条自己的帮助信息，但是有所校验

        .. admonition:: 注意
           :class: caution

           在一个 bot 实例的范围内，同命名空间同名称的共享对象，只能绑定一个回调方法。
           而且这个共享对象必须在本插件通过 :meth:`on_share` 注册（共享对象注册、共享对象回调绑定先后顺序不重要）

        :param namespace: 共享对象的命名空间
        :param id: 共享对象的 id 标识
        """

        def make_args(func: AsyncCallable[P, T]) -> AsyncCallable[P, T]:
            self.__share_cb_args__.append(
                ShareObjCbArgs(
                    namespace if namespace is not None else self.ID,
                    id,
                    DependManager.inject(func),
                )
            )
            return func

        return make_args

    def on_bot_life(self, *types: BotLife):
        """绑定 bot 在某个/某些生命周期的 hook 方法

        本方法作为异步函数的装饰器使用，此时可绑定一个函数为 bot 生命周期 hook 方法。

        .. code:: python

           # 假设存在一个名为 plugin 的变量，是 BotPlugin 实例
           # 我们希望这个插件，在 bot 连接器建立连接后给某人发一条消息
           @plugin.on_bot_life(BotLife.CONNECTED)
           async def say_hi() -> None:
               # melobot 对被装饰函数的要求：无参数，返回空值
               await send_custom("Hello~", isPrivate=True, userId=xxxxx)
           # 在这个示例中，bot 登录上号后，便会向 xxxxx 发送一条 Hello~ 消息

        :param types: bot 生命周期类型枚举值，可传入多个
        """

        def make_args(func: AsyncCallable[P, None]) -> AsyncCallable[P, None]:
            for type in types:
                self.__hook_args__.append(
                    BotHookRunnerArgs(DependManager.inject(func), type)
                )
            return func

        return make_args

    @property
    def on_bot_loaded(self):
        """绑定 bot 在 :attr:`.BotLife.LOADED` 生命周期的 hook 方法

        本方法作为异步函数的装饰器使用。用法与 :class:`on_bot_life` 类似。
        """
        return self.on_bot_life(BotLife.LOADED)

    @property
    def on_first_connected(self):
        """绑定 bot 在 :attr:`.BotLife.FIRST_CONNECTED` 生命周期的 hook 方法

        本方法作为异步函数的装饰器使用。用法与 :class:`on_bot_life` 类似。
        """
        return self.on_bot_life(BotLife.FIRST_CONNECTED)

    @property
    def on_reconnected(self):
        """绑定 bot 在 :attr:`.BotLife.RECONNECTED` 生命周期的 hook 方法

        本方法作为异步函数的装饰器使用。用法与 :class:`on_bot_life` 类似。
        """
        return self.on_bot_life(BotLife.RECONNECTED)

    @property
    def on_connected(self):
        """绑定 bot 在 :attr:`.BotLife.FIRST_CONNECTED` 和 :attr:`.BotLife.RECONNECTED` 生命周期的 hook 方法

        本方法作为异步函数的装饰器使用。用法与 :class:`on_bot_life` 类似。
        """
        return self.on_bot_life(BotLife.FIRST_CONNECTED, BotLife.RECONNECTED)

    @property
    def on_before_close(self):
        """绑定 bot 在 :attr:`.BotLife.BEFORE_CLOSE` 生命周期的 hook 方法

        本方法作为异步函数的装饰器使用。用法与 :class:`on_bot_life` 类似。
        """
        return self.on_bot_life(BotLife.BEFORE_CLOSE)

    @property
    def on_before_stop(self):
        """绑定 bot 在 :attr:`.BotLife.BEFORE_STOP` 生命周期的 hook 方法

        本方法作为异步函数的装饰器使用。用法与 :class:`on_bot_life` 类似。
        """
        return self.on_bot_life(BotLife.BEFORE_STOP)

    @property
    def on_event_built(self):
        """绑定 bot 在 :attr:`.BotLife.EVENT_BUILT` 生命周期的 hook 方法

        本方法作为异步函数的装饰器使用。用法与 :class:`on_bot_life` 类似。
        """
        return self.on_bot_life(BotLife.EVENT_BUILT)

    @property
    def on_action_presend(self):
        """绑定 bot 在 :attr:`.BotLife.ACTION_PRESEND` 生命周期的 hook 方法

        本方法作为异步函数的装饰器使用。用法与 :class:`on_bot_life` 类似。
        """
        return self.on_bot_life(BotLife.ACTION_PRESEND)
