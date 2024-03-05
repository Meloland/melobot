from abc import ABC, abstractmethod, abstractproperty

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

    def is_msg(self) -> bool:
        return self.type == "message"

    def is_req(self) -> bool:
        return self.type == "request"

    def is_notice(self) -> bool:
        return self.type == "notice"

    def is_meta(self) -> bool:
        return self.type == "meta"

    def is_resp(self) -> bool:
        return self.type == "response"

    def _get_args(self, parser_id: Any) -> dict[str, ParseArgs] | Literal[-1]:
        if self._args_map is None:
            return -1
        return self._args_map.get(parser_id, -1)

    def _store_args(self, parser_id: Any, args_group: dict[str, ParseArgs]) -> None:
        if self._args_map is None:
            self._args_map = {}
        self._args_map[parser_id] = args_group


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


# 插件共享对象构造参数
ShareObjArgs = NamedTuple("ShareObjArgs", property=str, namespace=str, id=str)
# 插件共享对象回调的构造参数
ShareCbArgs = NamedTuple("ShareCbArgs", namespace=str, id=str, cb=Callable)
# 插件信号方法构造参数
SignalHandlerArgs = NamedTuple(
    "SignalHandlerArgs", func=AsyncFunc[None], namespace=str, signal=str
)
# 钩子方法（生命周期回调）构造参数
HookRunnerArgs = NamedTuple("HookRunnerArgs", func=AsyncFunc[None], type=BotLife)
