import asyncio as aio
import json
from abc import ABC, abstractmethod, abstractproperty
from contextvars import ContextVar, Token
from copy import deepcopy

from .exceptions import BotActionError, BotCheckerError, BotMatcherError, TryFlagFailed
from .typing import (
    TYPE_CHECKING,
    Any,
    BotLife,
    Callable,
    Coroutine,
    Enum,
    ModuleType,
    Optional,
    ParseArgs,
    Type,
    Void,
    VoidType,
)

if TYPE_CHECKING:
    from ..bot.hook import BotHookBus
    from ..bot.init import MeloBot
    from ..controller.dispatcher import BotDispatcher
    from ..controller.responder import BotResponder
    from ..models.event import BotEventBuilder
    from ..plugin.handler import EventHandler
    from ..utils.logger import Logger


class AbstractConnector(ABC):
    def __init__(
        self,
        max_retry: int,
        retry_delay: float,
        cd_time: float,
    ) -> None:
        super().__init__()
        self.slack: bool = False
        self.max_retry = max_retry
        self.retry_delay = retry_delay if retry_delay > 0 else 0
        self.cd_time = cd_time

        self._ref_flag: bool = False
        self._ready_signal = aio.Event()

    @abstractmethod
    async def __aenter__(self):
        pass

    @abstractmethod
    async def __aexit__(
        self, exc_type: Type[Exception], exc_val: Exception, exc_tb: ModuleType
    ) -> bool:
        pass

    def _set_ready(self) -> None:
        self._ready_signal.set()

    @abstractmethod
    def _bind(
        self,
        dispatcher: "BotDispatcher",
        responder: "BotResponder",
        event_builder: Type["BotEventBuilder"],
        bot_bus: "BotHookBus",
        logger: "Logger",
    ) -> None:
        pass

    @abstractmethod
    async def _start_tasks(self) -> list[aio.Task]:
        pass

    @abstractmethod
    async def _send(self, action: "BotAction") -> None:
        pass


class Flagable:
    """
    可标记对象
    """

    def __init__(self) -> None:
        self._flags_store: Optional[dict[str, dict[str, Any]]] = None

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


class Cloneable:
    """
    可自我复制对象
    """

    def copy(self):
        """
        返回一个本对象的一个深拷贝对象
        """
        return deepcopy(self)


class BotEvent(ABC, Flagable):
    """
    Bot 事件类
    """

    def __init__(self, rawEvent: dict) -> None:
        super().__init__()
        self.raw = rawEvent
        self._args_map: Optional[dict[Any, dict[str, ParseArgs] | None]] = None

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

    def _get_args(self, parser_id: Any) -> dict[str, ParseArgs] | VoidType | None:
        if self._args_map is None:
            return Void
        return self._args_map.get(parser_id, Void)

    def _store_args(
        self, parser_id: Any, args_group: dict[str, ParseArgs] | None
    ) -> None:
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


class BotAction(Flagable, Cloneable):
    """
    Bot 行为类
    """

    def __init__(
        self,
        action_args: ActionArgs,
        resp_id: Optional[str] = None,
        triggerEvent: Optional[BotEvent] = None,
        ready: bool = False,
    ) -> None:
        super().__init__()
        # 只有 action 对应的响应需要被等待单独处理时，才会生成 id
        self.resp_id = resp_id
        self.type = action_args.type
        self.params = action_args.params
        self.trigger = triggerEvent
        self.ready = ready

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

    def flatten(self, indent: Optional[int] = None) -> str:
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


class EventHandlerArgs:
    """
    事件方法（事件执行器）构造参数
    """

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
    """
    插件共享对象构造参数
    """

    def __init__(
        self, namespace: str, id: str, reflector: Callable[[], Coroutine[Any, Any, Any]]
    ) -> None:
        self.reflector = reflector
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


class LogicMode(Enum):
    """
    逻辑模式枚举
    """

    AND = 1
    OR = 2
    NOT = 3
    XOR = 4

    @classmethod
    def calc(cls, logic: "LogicMode", v1: Any, v2: Any = None) -> bool:
        if logic == LogicMode.AND:
            return (v1 and v2) if v2 is not None else bool(v1)
        elif logic == LogicMode.OR:
            return (v1 or v2) if v2 is not None else bool(v1)
        elif logic == LogicMode.NOT:
            return not v1
        elif logic == LogicMode.XOR:
            return (v1 ^ v2) if v2 is not None else bool(v1)

    @classmethod
    def seq_calc(cls, logic: "LogicMode", values: list[Any]) -> bool:
        if len(values) <= 0:
            return False
        elif len(values) <= 1:
            return bool(values[0])

        idx = 0
        res: bool
        while idx < len(values):
            if idx == 0:
                res = cls.calc(logic, values[idx], values[idx + 1])
                idx += 1
            else:
                res = cls.calc(logic, res, values[idx])
            idx += 1
        return res


class BotChecker(ABC, Cloneable):
    def __init__(
        self,
        ok_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
        fail_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ) -> None:
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
        """
        后期指定 ok_cb 回调
        """
        if self.ok_cb is not None:
            raise BotCheckerError(f"ok_cb 回调已经被初始化，值为：{self.ok_cb}")
        self.ok_cb = ok_cb

    def _fill_fail_cb(self, fail_cb: Callable[[], Coroutine[Any, Any, None]]) -> None:
        """
        后期指定 fail_cb 回调
        """
        if self.fail_cb is not None:
            raise BotCheckerError(f"fail_cb 回调已经被初始化，值为：{self.fail_cb}")
        self.fail_cb = fail_cb

    @abstractmethod
    async def check(self, event: BotEvent) -> bool:
        pass


class WrappedChecker(BotChecker):
    """
    按逻辑关系工作的的合并检查器，使用 AND, OR, XOR 模式时，
    需要传递两个 checker。使用 NOT 时只需要传递第一个 checker
    """

    def __init__(
        self,
        mode: LogicMode,
        checker1: BotChecker,
        checker2: Optional[BotChecker] = None,
    ) -> None:
        super().__init__()
        self.mode = mode
        self.c1, self.c2 = checker1, checker2

    def _fill_ok_cb(self, ok_cb: Callable[[], Coroutine[Any, Any, None]]) -> None:
        """
        后期指定 ok_cb 回调，注意此时是联合检查器，
        因此将被自动应用到所包含的所有检查器
        """
        super()._fill_ok_cb(ok_cb)
        self.c1._fill_ok_cb(ok_cb)
        self.c2._fill_ok_cb(ok_cb) if self.c2 else None

    def _fill_fail_cb(self, fail_cb: Callable[[], Coroutine[Any, Any, None]]) -> None:
        """
        后期指定 fail_cb 回调，注意此时是联合检查器，
        因此将被自动应用到所包含的所有检查器
        """
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
        self,
        mode: LogicMode,
        matcher1: BotMatcher,
        matcher2: Optional[BotMatcher] = None,
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
    def parse(self, text: str) -> Optional[dict[str, ParseArgs]]:
        pass

    @abstractmethod
    def test(
        self, args_group: dict[str, ParseArgs] | None
    ) -> tuple[bool, Optional[str], Optional[ParseArgs]]:
        pass

    @abstractmethod
    async def format(self, cmd_name: str, args: ParseArgs) -> bool:
        pass


class BotLocal:
    """
    MeloBot 自动上下文
    """

    def __init__(self) -> None:
        object.__setattr__(self, "__storage__", ContextVar("melobot_ctx"))
        self.__storage__: ContextVar["MeloBot"]

    def __setattr__(self, __name: str, __value: Any) -> None:
        setattr(self.__storage__.get(), __name, __value)

    def __getattr__(self, __name: str) -> Any:
        return getattr(self.__storage__.get(), __name)

    def _add_ctx(self, ctx: "MeloBot") -> Token:
        return self.__storage__.set(ctx)

    def _del_ctx(self, token: Token) -> None:
        self.__storage__.reset(token)


BOT_LOCAL = BotLocal()
