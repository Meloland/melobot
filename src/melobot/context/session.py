import asyncio
import json
import time
from contextvars import ContextVar, Token

from ..base.abc import (
    BotAction,
    BotEvent,
    CustomSessionRule,
    Event_T,
    ParseArgs,
    SessionRule,
)
from ..base.exceptions import BotRuntimeError, BotSessionError, BotValueError
from ..base.tools import get_twin_event
from ..base.typing import (
    TYPE_CHECKING,
    Any,
    AsyncCallable,
    Callable,
    Generic,
    Literal,
    Optional,
    Type,
    Union,
    Void,
    VoidType,
    cast,
)

if TYPE_CHECKING:
    from ..models.event import MessageEvent
    from ..plugin.handler import EventHandler
    from .manage import BotSessionManager


class BotSession:
    """Bot会话类。不需要直接实例化，必须通过 BotSessionBuilder 构造。"""

    def __init__(
        self,
        event: Event_T,
        manager: Type["BotSessionManager"],
        space_tag: Optional["EventHandler"] = None,
    ) -> None:
        super().__init__()
        self.store: dict[str, Any] = {}
        self.event = event
        self.args: Union["ParseArgs", None] = None

        self._manager = manager

        self._free_signal = asyncio.Event()
        self._free_signal.set()

        # 会话是否挂起的标志。二者互为孪生反状态。由 BotSessionManager 修改和管理
        self._hup_signal, self._awake_signal = get_twin_event()

        # 用于标记该会话属于哪个会话空间，如果为 None 则表明是一次性 会话
        self._space_tag: Optional["EventHandler"] = space_tag
        self._expired = False

    def __format__(self, format_spec: str) -> str:
        match format_spec:
            case "hexid":
                return f"{id(self):#x}"
            case _:
                raise BotSessionError(f"未知的会话格式化标识符：{format_spec}")

    def __lshift__(self, another: "BotSession") -> None:
        """合并会话的存储内容"""
        self.store.update(another.store)
        self.args = another.args


class SessionLocal:
    """会话 自动上下文"""

    _ = lambda x: not x.startswith("__")
    __slots__ = tuple(filter(_, dir(BotSession))) + ("__storage__",)

    def __init__(self) -> None:
        object.__setattr__(self, "__storage__", ContextVar("session_ctx"))
        self.__storage__: ContextVar[BotSession | VoidType]

    def __format__(self, format_spec: str) -> str:
        match format_spec:
            case "hexid":
                try:
                    return f"{self._get_var():hexid}"
                except LookupError:
                    return "None"

            case _:
                raise BotSessionError(f"未知的 SessionLocal 格式化标识符：{format_spec}")

    def _get_var(self) -> BotSession:
        var = self.__storage__.get()
        if var is Void:
            raise LookupError("上下文当前为 Void，识别为跨 bot 通信")

        return cast(BotSession, var)

    def __setattr__(self, __name: str, __value: Any) -> None:
        setattr(self._get_var(), __name, __value)

    def __getattr__(self, __name: str) -> Any:
        return getattr(self._get_var(), __name)

    def _add_ctx(self, ctx: BotSession | VoidType) -> Token:
        return self.__storage__.set(ctx)

    def _del_ctx(self, token: Token) -> None:
        self.__storage__.reset(token)


SESSION_LOCAL = SessionLocal()


class LegacyRule(SessionRule[Event_T]):
    """传统会话规则类，等价于其他 bot 框架中的 session"""

    def __init__(self) -> None:
        super().__init__()

    def compare(self, e1: BotEvent, e2: BotEvent) -> bool:
        if not e2.is_msg_event():
            return False
        else:
            e1 = cast("MessageEvent", e1)
            e2 = cast("MessageEvent", e2)
            return e1.sender.id == e2.sender.id and e1.group_id == e2.group_id


class SessionOption(Generic[Event_T]):
    """会话配置类"""

    def __init__(
        self,
        rule: SessionRule[Event_T] | Callable[[Event_T, Event_T], bool] = LegacyRule[
            Event_T
        ](),
        second_pass: bool = True,
        conflict_wait: bool = True,
        conflict_cb: Optional[AsyncCallable[[], None]] = None,
        hold: bool = False,
    ) -> None:
        """创建一个会话配置

        :param rule: 会话规则，为空则使用默认会话规则
        :param second_pass: 会话暂停后，是否不进行预处理就唤醒会话
        :param conflict_wait: 会话冲突时，同会话事件是否等待处理
        :param conflict_cb: 会话冲突时，同会话事件不等待处理，转而运行的回调（`conflict_wait=False` 时生效）
        :param hold: 事件处理方法结束后是否保留会话
        """
        super().__init__()
        self.rule: SessionRule = (
            rule if isinstance(rule, SessionRule) else CustomSessionRule(rule)
        )
        self.second_pass = second_pass
        self.conflict_wait = conflict_wait
        self.conflict_cb = conflict_cb
        self.hold = hold


class ActionResponse:
    """行为响应类

    .. admonition:: 提示
       :class: tip

       一般无需手动实例化该类，多数情况会直接使用本类对象，或将本类用作类型注解。
    """

    def __init__(self, raw: dict | str) -> None:
        self.raw = raw if isinstance(raw, dict) else json.loads(raw)
        self.id: Optional[str] = None
        #: 响应的状态码
        self.status: int
        #: 响应的数据
        self.data: dict[str, Any]
        #: 响应创建的时间
        self.time: int = int(time.time())

        self.status = self.raw["retcode"]
        self.id = self.raw.get("echo")
        self.data = self.raw.get("data", {})

    def __format__(self, format_spec: str) -> str:
        match format_spec:
            case "hexid":
                return f"{id(self):#x}"
            case "raw":
                return self.raw.__str__()
            case _:
                raise BotValueError(f"未知的 resp 格式标识符：{format_spec}")

    def is_ok(self) -> bool:
        """是否为成功响应"""
        return self.raw["status"] == "ok"

    def is_processing(self) -> bool:
        """是否为被异步处理的响应，即未完成但在处理中"""
        return self.status == 202

    def is_failed(self) -> bool:
        """是否为失败响应"""
        return self.raw["status"] != "ok"


class ActionHandle:
    """行为操作类

    本类的实例是可等待对象。使用 await 会使行为操作尽快执行。不使用 await 会先创建异步任务，稍后执行

    .. admonition:: 提示
       :class: tip

       一般无需手动实例化该类，多数情况会直接使用本类对象，或将本类用作类型注解。
    """

    def __init__(
        self,
        action: "BotAction",
        exec_meth: AsyncCallable[["BotAction"], asyncio.Future[ActionResponse] | None],
        wait: bool,
    ) -> None:
        #: 本操作包含的行为对象
        self.action: "BotAction" = action
        #: 本操作当前状态。分别对应：未执行、执行中、执行完成
        self.status: Literal["PENDING", "EXECUTING", "FINISHED"] = "PENDING"

        self._resp: ActionResponse
        self._wait = wait
        self._exec_meth = exec_meth
        self._resp_done = asyncio.Event()

    @property
    async def resp(self) -> ActionResponse:
        """当前行为操作的响应数据，需要异步获取（行为操作函数 `wait` 参数为 :obj:`True` 时使用）"""
        if not self._wait:
            raise BotRuntimeError("行为操作未指定等待，无法获取响应")

        await self._resp_done.wait()
        return self._resp

    def __await__(self):
        yield

    async def wait(self) -> None:
        """等待当前行为操作完成（行为操作函数 `wait` 参数为 :obj:`True` 时使用）"""
        if not self._wait:
            raise BotRuntimeError("行为操作未指定等待，无法等待")
        await self._resp_done.wait()

    async def _execute(self) -> None:
        ret = await self._exec_meth(self.action)
        if self._wait:
            ret = cast(asyncio.Future[ActionResponse], ret)
            self._resp = await ret
            self._resp_done.set()

        self.status = "FINISHED"

    def execute(self) -> "ActionHandle":
        """手动触发行为操作的执行（行为操作函数 `auto` 参数为 :obj:`False` 时使用）

        :return: 本实例对象（因此支持链式调用）
        """
        if self.status != "PENDING":
            raise BotRuntimeError("行为操作正在执行或执行完毕，不应该再执行")

        self.status = "EXECUTING"
        asyncio.create_task(self._execute())
        return self
