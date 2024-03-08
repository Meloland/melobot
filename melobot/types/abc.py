import json
from abc import ABC, abstractmethod, abstractproperty
from asyncio import Future
from copy import deepcopy

from .exceptions import *
from .typing import *

if TYPE_CHECKING:
    from ..models.event import ResponseEvent


class AbstractSender(ABC):
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    async def send(self, action: "BotAction") -> None:
        pass


class AbstractResponder(ABC):
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    async def dispatch(self, resp: "ResponseEvent") -> None:
        pass

    @abstractmethod
    async def take_action(self, action: "BotAction") -> None:
        pass

    @abstractmethod
    async def take_action_wait(self, action: "BotAction") -> Future["ResponseEvent"]:
        pass


class AbstractDispatcher(ABC):
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    async def dispatch(self, event: "BotEvent") -> None:
        pass


class Flagable:
    """
    可标记对象
    """

    def __init__(self) -> None:
        self._flags_store: Dict[str, Dict[str, Any]] = None

    def mark(self, namespace: str, flag_name: str, val: Any = None) -> None:
        """
        为对象添加在指定命名空间下，名为 flag_name 的标记。
        此后此对象会一直携带此标记，无法撤销。
        """
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
        """
        检查此对象是否携带有指定的标记
        """
        self._flags_store = self._flags_store
        if self._flags_store is None:
            return False
        if (flags := self._flags_store.get(namespace)) is None:
            return False
        if (flag := flags.get(flag_name, Void)) is Void:
            return False
        return flag is val if val is None else flag == val


class BotEvent(ABC, Flagable):
    """
    Bot 事件类
    """

    def __init__(self, rawEvent: dict) -> None:
        super().__init__()
        self.raw = rawEvent
        self._args_map: Dict[Any, Dict[str, ParseArgs]] = None

    @abstractproperty
    def time(self) -> int:
        pass

    @abstractproperty
    def type(self) -> str:
        pass

    def is_msg_event(self) -> bool:
        return self.type == "message"

    def is_req_event(self) -> bool:
        return self.type == "request"

    def is_notice_event(self) -> bool:
        return self.type == "notice"

    def is_meta_event(self) -> bool:
        return self.type == "meta"

    def is_resp_event(self) -> bool:
        return self.type == "response"

    def _get_args(self, parser_id: Any) -> dict[str, ParseArgs] | Literal[-1]:
        if self._args_map is None:
            return -1
        return self._args_map.get(parser_id, -1)

    def _store_args(self, parser_id: Any, args_group: dict[str, ParseArgs]) -> None:
        if self._args_map is None:
            self._args_map = {}
        self._args_map[parser_id] = args_group


class ActionArgs(ABC):
    """
    行为信息构造基类
    """

    def __init__(self) -> None:
        super().__init__()
        self.type: str
        self.params: dict


class BotAction(Flagable):
    """
    Bot 行为类
    """

    def __init__(
        self,
        action_args: ActionArgs,
        resp_id: Optional[str] = None,
        triggerEvent: BotEvent = None,
        ready: bool = False,
    ) -> None:
        super().__init__()
        # 只有 action 对应的响应需要被等待单独处理时，才会生成 id
        self.resp_id = resp_id
        self.type = action_args.type
        self.params = action_args.params
        self.trigger = triggerEvent
        self.ready = ready

    def copy(self) -> "BotAction":
        """
        创建当前 action 的深拷贝
        """
        return deepcopy(self)

    def extract(self) -> dict:
        """
        从对象提取标准 cq action dict
        """
        obj = {
            "action": self.type,
            "params": self.params,
        }
        if self.resp_id:
            obj["echo"] = self.resp_id
        return obj

    def flatten(self, indent: int = None) -> str:
        """
        将对象序列化为标准 cq action json 字符串，一般供连接器使用
        """
        return json.dumps(self.extract(), ensure_ascii=False, indent=indent)

    def _fill_trigger(self, event: BotEvent) -> None:
        """
        后期指定触发 event
        """
        if self.trigger is None:
            self.trigger = event
            return
        raise BotActionError("action 已记录触发 event，拒绝再次记录")


class SessionRule(ABC):
    """
    用作 sesion 的区分依据
    """

    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    def compare(self, e1: BotEvent, e2: BotEvent) -> bool:
        pass


class ShareObjArgs:
    """
    插件共享对象构造参数
    """

    def __init__(self, property: str, namespace: str, id: str) -> None:
        self.property = property
        self.namespace = namespace
        self.id = id


class ShareObjCbArgs:
    """
    插件共享对象回调的构造参数
    """

    def __init__(
        self, namespace: str, id: str, cb: Callable[..., Coroutine[Any, Any, Any]]
    ) -> None:
        self.namespace = namespace
        self.id = id
        self.cb = cb


class PluginSignalHandlerArgs:
    """
    插件信号方法构造参数
    """

    def __init__(
        self, func: Callable[..., Coroutine[Any, Any, Any]], namespace: str, signal: str
    ) -> None:
        self.func = func
        self.namespace = namespace
        self.signal = signal


class BotHookRunnerArgs:
    """
    钩子方法（生命周期回调）构造参数
    """

    def __init__(
        self, func: Callable[..., Coroutine[Any, Any, None]], type: BotLife
    ) -> None:
        self.func = func
        self.type = type


class BotChecker(ABC):
    def __init__(self) -> None:
        super().__init__()

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

    def __invert__(self) -> "WrappedMatcher":
        return WrappedChecker(LogicMode.NOT, self)

    def __xor__(self, other: "BotChecker") -> "WrappedChecker":
        if not isinstance(other, BotChecker):
            raise BotCheckerError(
                f"联合检查器定义时出现了非检查器对象，其值为：{other}"
            )
        return WrappedChecker(LogicMode.XOR, self, other)

    @abstractmethod
    def check(self, event: BotEvent) -> bool:
        pass


class WrappedChecker(BotChecker):
    """
    按逻辑关系工作的的合并检查器，使用 AND, OR, XOR 模式时，
    需要传递两个 checker。使用 NOT 时只需要传递第一个 checker
    """

    def __init__(
        self, mode: LogicMode, checker1: BotChecker, checker2: BotChecker = None
    ) -> None:
        super().__init__()
        self.mode = mode
        self.c1, self.c2 = checker1, checker2

    def check(self, event: BotEvent) -> bool:
        return LogicMode.calc(
            self.mode,
            self.c1.check(event),
            self.c2.check(event) if self.c2 is not None else None,
        )


class BotMatcher(ABC):
    def __init__(self) -> None:
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
        pass


class WrappedMatcher(BotMatcher):
    """
    按逻辑关系工作的的合并匹配器，使用 AND, OR, XOR 模式时，
    需要传递两个 matcher。使用 NOT 时只需要传递第一个 matcher
    """

    def __init__(
        self, mode: LogicMode, matcher1: BotMatcher, matcher2: BotMatcher = None
    ) -> None:
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
    """
    解析器基类。解析器一般用作从消息文本中按规则提取指定字符串或字符串组合
    """

    def __init__(self, id: Any) -> None:
        super().__init__()
        self.id = id
        self.need_format: bool = False

    @abstractmethod
    def parse(self, text: str) -> Optional[Dict[str, ParseArgs]]:
        pass

    @abstractmethod
    def test(
        self, args_group: Dict[str, ParseArgs]
    ) -> Tuple[bool, Optional[str], Optional[ParseArgs]]:
        pass

    @abstractmethod
    def format(
        self,
        custom_msg_func: Callable[..., Coroutine[Any, Any, "ResponseEvent"]],
        cmd_name: str,
        event: BotEvent,
        args: ParseArgs,
    ) -> bool:
        pass
