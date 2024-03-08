import json
from abc import ABC, abstractmethod, abstractproperty
from copy import deepcopy

from .exceptions import *
from .typing import *


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


class BotLife(Enum):
    """
    bot 生命周期枚举
    """

    LOADED = 1
    CONNECTED = 2
    BEFORE_CLOSE = 3
    BEFORE_STOP = 4
    EVENT_BUILT = 5
    ACTION_PRESEND = 6


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
