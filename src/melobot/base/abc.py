import asyncio
import json
from abc import ABC, abstractmethod
from copy import deepcopy

from .exceptions import (
    BotActionError,
    BotCheckerError,
    BotMatcherError,
    BotValueError,
    TryFlagFailed,
    get_better_exc,
)
from .typing import (
    TYPE_CHECKING,
    Any,
    BotLife,
    Callable,
    Coroutine,
    Literal,
    LogicMode,
    ModuleType,
    Optional,
    ParseArgs,
    Type,
    Void,
    VoidType,
)

if TYPE_CHECKING:
    import logging

    from ..bot.hook import BotHookBus
    from ..controller.dispatcher import BotDispatcher
    from ..controller.responder import BotResponder
    from ..models.event import BotEventBuilder
    from ..plugin.handler import EventHandler


class AbstractConnector(ABC):
    """抽象连接器类

    .. admonition:: 提示
       :class: tip

       一般无需手动实例化该类，多数情况会直接使用本类对象，或将本类用作类型注解。
    """

    def __init__(self, cd_time: float) -> None:
        super().__init__()
        #: 连接器的日志器
        self.logger: "logging.Logger"
        #: 是否在 slack 状态
        self.slack: bool = False
        #: 连接器发送行为操作的冷却时间
        self.cd_time = cd_time

        self._used: bool = False
        self._ready_signal = asyncio.Event()
        self._event_builder: Type["BotEventBuilder"]
        self._bot_bus: "BotHookBus"
        self._common_dispatcher: "BotDispatcher"
        self._resp_dispatcher: "BotResponder"

    @abstractmethod
    async def __aenter__(self):
        pass

    @abstractmethod
    async def __aexit__(
        self, exc_type: Type[Exception], exc_val: Exception, exc_tb: ModuleType
    ) -> bool:
        if exc_type is None:
            return True
        elif exc_type == asyncio.CancelledError:
            return True
        else:
            self.logger.error(f"连接器出现预期外的异常：\n{get_better_exc(exc_val)}")
            return False

    def _set_ready(self) -> None:
        self._ready_signal.set()

    def _bind(
        self,
        dispatcher: "BotDispatcher",
        responder: "BotResponder",
        event_builder: Type["BotEventBuilder"],
        bot_bus: "BotHookBus",
        logger: "logging.Logger",
    ) -> None:
        self._event_builder = event_builder
        self._bot_bus = bot_bus
        self.logger = logger
        self._common_dispatcher = dispatcher
        self._resp_dispatcher = responder

    @abstractmethod
    async def _send(self, action: "BotAction") -> None:
        pass


class Flagable:
    def __init__(self) -> None:
        self._flags_store: Optional[dict[str, dict[str, Any]]] = None

    def mark(self, namespace: str, flag_name: str, val: Any = None) -> None:
        """为对象添加在指定命名空间下，名为 flag_name 的标记。 此后此对象会一直携带此标记，无法撤销。"""
        if self._flags_store is None:
            self._flags_store = {}
        if self._flags_store.get(namespace) is None:
            self._flags_store[namespace] = {}
        if flag_name in self._flags_store[namespace].keys():
            raise TryFlagFailed(
                f"对象不可被重复标记。在命名空间 {namespace} 中名为 {flag_name} 的标记已存在"
            )
        self._flags_store[namespace][flag_name] = val

    def flag_check(self, namespace: str, flag_name: str, val: Any = None) -> bool:
        """检查此对象是否携带有指定的标记"""
        self._flags_store = self._flags_store
        if self._flags_store is None:
            return False
        if (flags := self._flags_store.get(namespace)) is None:
            return False
        if (flag := flags.get(flag_name, Void)) is Void:
            return False
        return flag is val if val is None else flag == val


class Cloneable:
    def copy(self):
        """返回一个本对象的一个深拷贝对象"""
        return deepcopy(self)


class BotEvent(ABC, Flagable):
    """事件基类

    .. admonition:: 提示
       :class: tip

       一般无需手动实例化该类，多数情况会直接使用本类对象，或将本类用作类型注解。
    """

    def __init__(self, rawEvent: dict) -> None:
        super().__init__()
        #: 从 onebot 实现项目获得的未格式化的事件原始值
        self.raw: dict = rawEvent
        self._args_map: Optional[dict[Any, dict[str, ParseArgs] | None]] = None

    def __format__(self, format_spec: str) -> str:
        match format_spec:
            case "hexid":
                return f"{id(self):#x}"
            case "raw":
                return self.raw.__str__()
            case _:
                raise BotValueError(f"未知的 event 格式标识符：{format_spec}")

    @property
    @abstractmethod
    def time(self) -> int:
        """事件发生的时间"""
        pass

    @property
    @abstractmethod
    def type(self) -> Literal["message", "request", "notice", "meta", "response"]:
        """事件类型"""
        pass

    def is_msg_event(self) -> bool:
        """判断是否是消息事件"""
        return self.type == "message"

    def is_req_event(self) -> bool:
        """判断是否是请求事件"""
        return self.type == "request"

    def is_notice_event(self) -> bool:
        """判断是否是通知事件"""
        return self.type == "notice"

    def is_meta_event(self) -> bool:
        """判断是否是元事件"""
        return self.type == "meta"

    def is_resp_event(self) -> bool:
        """判断是否是响应事件"""
        return self.type == "response"

    def _get_args(self, parser_id: Any) -> dict[str, ParseArgs] | VoidType | None:
        if self._args_map is None:
            return Void
        return self._args_map.get(parser_id, Void)

    def _store_args(
        self, parser_id: Any, args_dict: dict[str, ParseArgs] | None
    ) -> None:
        if self._args_map is None:
            self._args_map = {}
        self._args_map[parser_id] = args_dict


class ActionArgs(ABC):
    # 行为信息构造基类

    def __init__(self) -> None:
        super().__init__()
        self.type: str
        self.params: dict


class BotAction(Flagable, Cloneable):
    """行为类

    每个行为操作应该产生一个行为对象

    .. admonition:: 提示
       :class: tip

       一般无需手动实例化该类，多数情况会直接使用本类对象，或将本类用作类型注解。
    """

    def __init__(
        self,
        action_args: ActionArgs,
        resp_id: Optional[str] = None,
        triggerEvent: Optional[BotEvent] = None,
        ready: bool = False,
    ) -> None:
        super().__init__()
        self.resp_id = resp_id
        #: 行为类型。对应 onebot 标准中的 API 终结点名称
        self.type: str = action_args.type
        #: 行为参数。对应 onebot 标准中向 API 传送的数据的 params 字段
        self.params: dict = action_args.params
        #: 行为的触发事件，一般是行为生成时所在会话的事件
        self.trigger: Optional[BotEvent] = triggerEvent

        self._ready = ready

    def __format__(self, format_spec: str) -> str:
        match format_spec:
            case "hexid":
                return f"{id(self):#x}"
            case "raw":
                trigger = (
                    f"{self.trigger.__class__.__name__}[{self.trigger:hexid}]"
                    if self.trigger is not None
                    else None
                )
                return (
                    f"BotAction(type={self.type}, trigger={trigger}, "
                    f"resp_id={self.resp_id}, params={self.params})"
                )
            case _:
                raise BotValueError(f"未知的 action 格式标识符：{format_spec}")

    def extract(self) -> dict:
        # 从对象提取标准 cq action dict
        obj = {
            "action": self.type,
            "params": self.params,
        }
        if self.resp_id:
            obj["echo"] = self.resp_id
        return obj

    def flatten(self, indent: Optional[int] = None) -> str:
        # 将对象序列化为标准 cq action json 字符串，一般供连接器使用
        return json.dumps(self.extract(), ensure_ascii=False, indent=indent)

    def _fill_trigger(self, event: BotEvent) -> None:
        # 后期指定触发 event
        if self.trigger is None:
            self.trigger = event
            return
        raise BotActionError("action 已记录触发 event，拒绝再次记录")


class SessionRule(ABC):
    """会话规则基类

    会话规则用于两事件是否在同一会话的判断。
    """

    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    def compare(self, e1: BotEvent, e2: BotEvent) -> bool:
        """判断两事件是否在同一会话中的判断方法

        任何会话规则应该实现此抽象方法。

        :param e1: 判断时的事件1
        :param e2: 判断时的事件2
        :return: 判断结果
        """
        pass


class EventHandlerArgs:
    """事件方法（事件执行器）构造参数"""

    def __init__(
        self,
        executor: Callable[[], Coroutine[Any, Any, None]],
        type: Type["EventHandler"],
        params: list[Any],
    ) -> None:
        self.executor = executor
        self.type = type
        self.params = params


class ShareObjArgs:
    """插件共享对象构造参数"""

    def __init__(
        self, namespace: str, id: str, reflector: Callable[[], Coroutine[Any, Any, Any]]
    ) -> None:
        self.reflector = reflector
        self.namespace = namespace
        self.id = id


class ShareObjCbArgs:
    """插件共享对象回调的构造参数"""

    def __init__(
        self, namespace: str, id: str, cb: Callable[..., Coroutine[Any, Any, Any]]
    ) -> None:
        self.namespace = namespace
        self.id = id
        self.cb = cb


class PluginSignalHandlerArgs:
    """插件信号方法构造参数"""

    def __init__(
        self, func: Callable[..., Coroutine[Any, Any, Any]], namespace: str, signal: str
    ) -> None:
        self.func = func
        self.namespace = namespace
        self.signal = signal


class BotHookRunnerArgs:
    """钩子方法（生命周期回调）构造参数"""

    def __init__(
        self, func: Callable[..., Coroutine[Any, Any, None]], type: BotLife
    ) -> None:
        self.func = func
        self.type = type


class BotChecker(ABC, Cloneable):
    """检查器基类"""

    def __init__(
        self,
        ok_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
        fail_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ) -> None:
        """初始化一个检查器基类对象

        :param ok_cb: 检查通过的回调
        :param fail_cb: 检查不通过的回调
        """
        super().__init__()
        self.ok_cb = ok_cb
        self.fail_cb = fail_cb

    def __and__(self, other: "BotChecker") -> "WrappedChecker":
        if not isinstance(other, BotChecker):
            raise BotCheckerError(
                f"联合检查器定义时出现了非检查器对象，其值为：{other}"
            )
        return WrappedChecker(LogicMode.AND, self, other)

    def __or__(self, other: "BotChecker") -> "WrappedChecker":
        if not isinstance(other, BotChecker):
            raise BotCheckerError(
                f"联合检查器定义时出现了非检查器对象，其值为：{other}"
            )
        return WrappedChecker(LogicMode.OR, self, other)

    def __invert__(self) -> "WrappedChecker":
        return WrappedChecker(LogicMode.NOT, self)

    def __xor__(self, other: "BotChecker") -> "WrappedChecker":
        if not isinstance(other, BotChecker):
            raise BotCheckerError(
                f"联合检查器定义时出现了非检查器对象，其值为：{other}"
            )
        return WrappedChecker(LogicMode.XOR, self, other)

    def _fill_ok_cb(self, ok_cb: Callable[[], Coroutine[Any, Any, None]]) -> None:
        """后期指定 ok_cb 回调"""
        if self.ok_cb is not None:
            raise BotCheckerError(f"ok_cb 回调已经被初始化，值为：{self.ok_cb}")
        self.ok_cb = ok_cb

    def _fill_fail_cb(self, fail_cb: Callable[[], Coroutine[Any, Any, None]]) -> None:
        """后期指定 fail_cb 回调"""
        if self.fail_cb is not None:
            raise BotCheckerError(f"fail_cb 回调已经被初始化，值为：{self.fail_cb}")
        self.fail_cb = fail_cb

    @abstractmethod
    async def check(self, event: BotEvent) -> bool:
        """检查器检查方法

        任何检查器应该实现此抽象方法。

        :param event: 给定的事件
        :return: 检查是否通过
        """
        pass


class WrappedChecker(BotChecker):
    """合并检查器

    在两个 :class:`BotChecker` 对象间使用 | & ^ ~ 运算符即可返回合并检查器。

    .. admonition:: 提示
       :class: tip

       一般无需手动实例化该类，多数情况会直接使用本类对象，或将本类用作类型注解。
    """

    def __init__(
        self,
        mode: LogicMode,
        checker1: BotChecker,
        checker2: Optional[BotChecker] = None,
    ) -> None:
        """初始化一个合并检查器

        :param mode: 合并检查的逻辑模式
        :param checker1: 检查器1
        :param checker2: 检查器2
        """
        super().__init__()
        self.mode = mode
        self.c1, self.c2 = checker1, checker2

    def _fill_ok_cb(self, ok_cb: Callable[[], Coroutine[Any, Any, None]]) -> None:
        """后期指定 ok_cb 回调，注意此时是联合检查器， 因此将被自动应用到所包含的所有检查器"""
        super()._fill_ok_cb(ok_cb)
        self.c1._fill_ok_cb(ok_cb)
        self.c2._fill_ok_cb(ok_cb) if self.c2 else None

    def _fill_fail_cb(self, fail_cb: Callable[[], Coroutine[Any, Any, None]]) -> None:
        """后期指定 fail_cb 回调，注意此时是联合检查器， 因此将被自动应用到所包含的所有检查器"""
        super()._fill_fail_cb(fail_cb)
        self.c1._fill_fail_cb(fail_cb)
        self.c2._fill_fail_cb(fail_cb) if self.c2 else None

    async def check(self, event: BotEvent) -> bool:
        return LogicMode.calc(
            self.mode,
            await self.c1.check(event),
            (await self.c2.check(event)) if self.c2 is not None else None,
        )


class BotMatcher(ABC, Cloneable):
    """匹配器基类"""

    def __init__(self) -> None:
        """初始化一个检查器基类对象"""
        super().__init__()

    def __and__(self, other: "BotMatcher") -> "WrappedMatcher":
        if not isinstance(other, BotMatcher):
            raise BotMatcherError(
                f"联合匹配器定义时出现了非匹配器对象，其值为：{other}"
            )
        return WrappedMatcher(LogicMode.AND, self, other)

    def __or__(self, other: "BotMatcher") -> "WrappedMatcher":
        if not isinstance(other, BotMatcher):
            raise BotMatcherError(
                f"联合匹配器定义时出现了非匹配器对象，其值为：{other}"
            )
        return WrappedMatcher(LogicMode.OR, self, other)

    def __invert__(self) -> "WrappedMatcher":
        return WrappedMatcher(LogicMode.NOT, self)

    def __xor__(self, other: "BotMatcher") -> "WrappedMatcher":
        if not isinstance(other, BotMatcher):
            raise BotMatcherError(
                f"联合匹配器定义时出现了非匹配器对象，其值为：{other}"
            )
        return WrappedMatcher(LogicMode.XOR, self, other)

    @abstractmethod
    def match(self, text: str) -> bool:
        """匹配器匹配方法

        任何匹配器应该实现此抽象方法。

        :param text: 消息事件的文本内容
        :return: 是否匹配
        """
        pass


class WrappedMatcher(BotMatcher):
    """合并匹配器

    在两个 :class:`BotMatcher` 对象间使用 | & ^ ~ 运算符即可返回合并匹配器

    .. admonition:: 提示
       :class: tip

       一般无需手动实例化该类，多数情况会直接使用本类对象，或将本类用作类型注解。
    """

    def __init__(
        self,
        mode: LogicMode,
        matcher1: BotMatcher,
        matcher2: Optional[BotMatcher] = None,
    ) -> None:
        """初始化一个合并匹配器

        :param mode: 合并匹配的逻辑模式
        :param matcher1: 匹配器1
        :param matcher2: 匹配器2
        """
        super().__init__()
        self.mode = mode
        self.m1, self.m2 = matcher1, matcher2

    def match(self, text: str) -> bool:
        return LogicMode.calc(
            self.mode,
            self.m1.match(text),
            self.m2.match(text) if self.m2 is not None else None,
        )


class BotParser(ABC):
    """解析器基类

    解析器一般用作从消息文本中按规则批量提取参数
    """

    def __init__(self, id: Any) -> None:
        """初始化一个解析器

        :param id: 解析器解析规则的标识

           id 相同，意味着解析规则相同。一组解析规则相同的解析器，只有第一个会实际运行解析。其他后续解析器会复用这个解析结果。

           id 标识存在的意义是增强复用性。如果你不需要复用，id 值给定不同的随机值即可。
        """
        super().__init__()
        #: 解析器的 id，即解析规则的表示
        self.id: Any = id
        #: 是否需要格式化（此属性可在继承后进行修改，若为否，则不再进行格式化）
        self.need_format: bool = False

    @abstractmethod
    def parse(self, text: str) -> Optional[dict[str, ParseArgs]]:
        """解析方法

        任何解析器应该实现此抽象方法

        :param text: 消息文本内容
        :return: 解析结果

           因为一次解析可能会得到多组结果，结果为字典或空值。字典键为一组解析结果的识别标志（例如命令解析中的命令名），值为解析参数对象（象征一组解析结果）
        """
        pass

    @abstractmethod
    def test(
        self, args_dict: Optional[dict[str, ParseArgs]]
    ) -> tuple[bool, Optional[str], Optional[ParseArgs]]:
        """解析测试方法

        任何解析器应该实现此抽象方法

        :param args_dict: 之前的解析结果
        :return: 返回元组：(判断是否解析成功, 可为空的一组解析结果的识别标志, 可为空的解析参数对象)
        """
        pass

    @abstractmethod
    async def format(self, group_id: str, args: ParseArgs) -> bool:
        """格式化方法

        任何解析器应该实现此抽象方法

        格式化是否进行，会受解析器 `need_fotmat` 参数和 :meth:`~.BotParser.test` 的影响。
        如果你确定你的解析器子类 100% 不需要格式化，那么继承这个方法再次标记为 pass 即可。

        格式化过程最后只返回是否格式化成功，格式化的结果将会被直接保存，并可通过 :func:`.msg_args` 获得。

        :param group_id: 一组解析结果的识别标志
        :param args: 解析参数对象
        :return: 格式化是否成功
        """
        pass
