import asyncio
import json
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass
from logging import CRITICAL, DEBUG, ERROR, INFO, WARNING, Logger

from .exceptions import BotRuntimeError, BotUtilsError, BotValueError
from .typing import (
    TYPE_CHECKING,
    Any,
    AsyncCallable,
    BotLife,
    Literal,
    LogicMode,
    ModuleType,
    Optional,
    ParseArgs,
    Type,
    Void,
)

if TYPE_CHECKING:
    from ..bot.hook import BotHookBus
    from ..controller.dispatcher import BotDispatcher
    from ..controller.responder import BotResponder
    from ..models.event import BotEventBuilder
    from ..plugin.handler import EventHandler


class BaseLogger(Logger):
    """日志器基类

    .. admonition:: 提示
       :class: tip

       一般无需手动实例化该类，多数情况会直接使用本类对象，或将本类用作类型注解。
    """

    LEVEL_MAP = {
        "DEBUG": DEBUG,
        "INFO": INFO,
        "WARNING": WARNING,
        "ERROR": ERROR,
        "CRITICAL": CRITICAL,
    }

    LEVEL_FLAG_NAME = "__LOG_LEVEL_FLAG__"

    def __init__(self, name: str, level: int) -> None:
        super().__init__(name, level)
        setattr(self, BaseLogger.LEVEL_FLAG_NAME, level)

    def check_level_flag(
        self, level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    ) -> bool:
        """检查日志器是否可以输出指定日志等级的日志"""
        return BaseLogger.LEVEL_MAP[level] >= getattr(self, BaseLogger.LEVEL_FLAG_NAME)

    LEVEL_CHECK_METH_NAME = check_level_flag.__name__


class AbstractConnector(ABC):
    """抽象连接器类

    .. admonition:: 提示
       :class: tip

       一般无需手动实例化该类，多数情况会直接使用本类对象，或将本类用作类型注解。
    """

    def __init__(self, cd_time: float) -> None:
        super().__init__()
        #: 连接器的日志器
        self.logger: BaseLogger
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
        raise NotImplementedError

    @abstractmethod
    async def __aexit__(
        self, exc_type: Type[Exception], exc_val: Exception, exc_tb: ModuleType
    ) -> bool:
        if exc_type is None:
            return True
        elif exc_type == asyncio.CancelledError:
            return True
        else:
            return False

    def _set_ready(self) -> None:
        self._ready_signal.set()

    def _bind(
        self,
        dispatcher: "BotDispatcher",
        responder: "BotResponder",
        event_builder: Type["BotEventBuilder"],
        bot_bus: "BotHookBus",
        logger: BaseLogger,
    ) -> None:
        self._event_builder = event_builder
        self._bot_bus = bot_bus
        self.logger = logger
        self._common_dispatcher = dispatcher
        self._resp_dispatcher = responder

    @abstractmethod
    async def _send(self, action: "BotAction") -> None:
        raise NotImplementedError


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
            raise BotUtilsError(
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
        #: 从 onebot 实现获得的事件原始值
        self.raw: dict = rawEvent

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
        raise NotImplementedError

    @property
    @abstractmethod
    def type(self) -> Literal["message", "request", "notice", "meta"]:
        """事件类型"""
        raise NotImplementedError

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


class ActionArgs(ABC):
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
        #: 行为的触发事件，一般是行为生成时所在会话的事件（大多数行为操作函数生成 :class:`.BotAction` 对象时，会自动填充此属性，但少数情况下此属性可能为空）
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
        raise BotRuntimeError("action 已记录触发它的 event，拒绝再次记录")


class SessionRule(ABC):
    """会话规则基类

    会话规则用于判断两事件是否在同一会话中。
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
        raise NotImplementedError


@dataclass
class EventHandlerArgs:
    """事件方法（事件执行器）构造参数"""

    executor: AsyncCallable[..., None]
    type: Type["EventHandler"]
    params: list[Any]


@dataclass
class ShareObjArgs:
    """插件共享对象构造参数"""

    reflector: AsyncCallable[..., Any]
    namespace: str
    id: str


@dataclass
class ShareObjCbArgs:
    """插件共享对象回调的构造参数"""

    namespace: str
    id: str
    cb: AsyncCallable[..., Any]


@dataclass
class PluginSignalHandlerArgs:
    """插件信号方法构造参数"""

    func: AsyncCallable[..., Any]
    namespace: str
    signal: str


@dataclass
class BotHookRunnerArgs:
    """钩子方法（生命周期回调）构造参数"""

    func: AsyncCallable[..., None]
    type: BotLife


class BotChecker(ABC, Cloneable):
    """检查器基类"""

    def __init__(self) -> None:
        """初始化一个检查器基类对象"""
        super().__init__()

    def __and__(self, other: "BotChecker") -> "WrappedChecker":
        if not isinstance(other, BotChecker):
            raise BotUtilsError(f"联合检查器定义时出现了非检查器对象，其值为：{other}")
        return WrappedChecker(LogicMode.AND, self, other)

    def __or__(self, other: "BotChecker") -> "WrappedChecker":
        if not isinstance(other, BotChecker):
            raise BotUtilsError(f"联合检查器定义时出现了非检查器对象，其值为：{other}")
        return WrappedChecker(LogicMode.OR, self, other)

    def __invert__(self) -> "WrappedChecker":
        return WrappedChecker(LogicMode.NOT, self)

    def __xor__(self, other: "BotChecker") -> "WrappedChecker":
        if not isinstance(other, BotChecker):
            raise BotUtilsError(f"联合检查器定义时出现了非检查器对象，其值为：{other}")
        return WrappedChecker(LogicMode.XOR, self, other)

    @abstractmethod
    async def check(self, event: BotEvent) -> bool:
        """检查器检查方法

        任何检查器应该实现此抽象方法。

        :param event: 给定的事件
        :return: 检查是否通过
        """
        raise NotImplementedError


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
            raise BotUtilsError(f"联合匹配器定义时出现了非匹配器对象，其值为：{other}")
        return WrappedMatcher(LogicMode.AND, self, other)

    def __or__(self, other: "BotMatcher") -> "WrappedMatcher":
        if not isinstance(other, BotMatcher):
            raise BotUtilsError(f"联合匹配器定义时出现了非匹配器对象，其值为：{other}")
        return WrappedMatcher(LogicMode.OR, self, other)

    def __invert__(self) -> "WrappedMatcher":
        return WrappedMatcher(LogicMode.NOT, self)

    def __xor__(self, other: "BotMatcher") -> "WrappedMatcher":
        if not isinstance(other, BotMatcher):
            raise BotUtilsError(f"联合匹配器定义时出现了非匹配器对象，其值为：{other}")
        return WrappedMatcher(LogicMode.XOR, self, other)

    @abstractmethod
    async def match(self, text: str) -> bool:
        """匹配器匹配方法

        任何匹配器应该实现此抽象方法。

        :param text: 消息事件的文本内容
        :return: 是否匹配
        """
        raise NotImplementedError


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

    async def match(self, text: str) -> bool:
        return LogicMode.calc(
            self.mode,
            self.m1.match(text),
            self.m2.match(text) if self.m2 is not None else None,
        )


class BotParser(ABC):
    """解析器基类

    解析器一般用作从消息文本中按规则批量提取参数
    """

    @abstractmethod
    async def parse(self, text: str) -> Optional[ParseArgs]:
        """解析方法

        任何解析器应该实现此抽象方法

        :param text: 消息文本内容
        :return: 解析结果

        """
        raise NotImplementedError
