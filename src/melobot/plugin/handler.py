import asyncio

from ..base.abc import BotParser
from ..base.exceptions import BotValueError, FuncSafeExited
from ..base.typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Optional,
    PriorLevel,
    T,
    Type,
    Union,
    Void,
    cast,
)
from ..context.session import SESSION_LOCAL, BotSessionManager, any_event
from ..utils.logger import log_exc

if TYPE_CHECKING:
    from ..base.abc import BotChecker, BotMatcher, SessionRule
    from ..context.session import BotSession
    from ..models.event import MessageEvent, MetaEvent, NoticeEvent, RequestEvent
    from ..utils.logger import BotLogger
    from .init import BotPlugin


class EventHandler:
    def __init__(
        self,
        executor: Callable[[], Coroutine[Any, Any, None]],
        plugin: "BotPlugin",
        logger: "BotLogger",
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        set_block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = True,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine]] = None,
    ) -> None:
        super().__init__()
        self.is_valid = True

        self.executor = executor
        self.logger = logger
        self.checker = checker
        self.priority = priority
        self.set_block = set_block
        self.temp = temp

        self._run_lock = asyncio.Lock()
        self._rule = session_rule
        self._hold = session_hold
        self._plugin = plugin
        self._direct_rouse = direct_rouse
        self._conflict_cb = conflict_cb
        self._wait_flag = conflict_wait

        if conflict_wait and conflict_cb:
            raise BotValueError("参数 conflict_wait 为 True 时，冲突回调永远不会被调用")

    def __format__(self, format_spec: str) -> str:
        match format_spec:
            case "hexid":
                return f"{id(self):#x}"
            case _:
                raise BotValueError(f"未知的 EventHandler 格式化标识符：{format_spec}")

    async def _verify(self) -> bool:
        """验证事件是否有触发执行的资格（验权）"""
        if self.checker:
            return await self.checker.check(any_event())
        return True

    async def _run_on_ctx(
        self,
        coro: Coroutine[Any, Any, T],
        session: "BotSession",
        timeout: Optional[float] = None,
    ) -> T:
        """在指定 session 上下文中运行协程。异常将会抛出"""
        try:
            s_token = SESSION_LOCAL._add_ctx(session)
            return await asyncio.wait_for(asyncio.create_task(coro), timeout=timeout)
        finally:
            SESSION_LOCAL._del_ctx(s_token)
            # 这里可能因 bot 停止运行，导致退出事件执行方法时 session 为挂起态。因此需要强制唤醒
            if session._hup_signal.is_set():
                BotSessionManager._rouse(session)

    async def _run(
        self,
        event: Union["MessageEvent", "RequestEvent", "MetaEvent", "NoticeEvent"],
        pre_session: "BotSession",
    ) -> None:
        """获取 session 然后准备运行 executor"""
        try:
            session = None
            if not self._direct_rouse:
                res = await BotSessionManager.try_attach(event, self)
                if res:
                    return
            session = await BotSessionManager.get(event, self)
            # 如果因为冲突没有获得 session，且指定了冲突回调
            if session is None and self._conflict_cb:
                await self._run_on_ctx(self._conflict_cb(), pre_session)
            # 如果因为冲突没有获得 session，但没有冲突回调
            if session is None:
                return
            # 如果没有冲突，正常获得到了 session
            exec_coro = self.executor()
            self.logger.debug(
                f"event {event:hexid} 准备在 session {session:hexid} 中处理"
            )
            session << pre_session
            await self._run_on_ctx(exec_coro, session)
        except FuncSafeExited:
            pass
        except Exception as e:
            executor_name = self.executor.__qualname__
            self.logger.error(
                f"插件 {self._plugin.ID} 事件处理方法 {executor_name} 发生异常"
            )
            self.logger.error(f"异常点 event：{event:hexid}\n{event:raw}")
            log_exc(self.logger, locals(), e)
        finally:
            if session is None:
                return
            self.logger.debug(
                f"event {event:hexid} 在 session {session:hexid} 中运行完毕"
            )
            BotSessionManager.recycle(session, alive=self._hold)

    async def _pre_process(
        self, event: Union["MessageEvent", "RequestEvent", "MetaEvent", "NoticeEvent"]
    ) -> tuple[bool, "BotSession"]:
        session = BotSessionManager.make_temp(event)
        status = await self._run_on_ctx(self._verify(), session)
        return status, session

    async def evoke(
        self, event: Union["MessageEvent", "RequestEvent", "MetaEvent", "NoticeEvent"]
    ) -> bool:
        """接收总线分发的事件的方法。返回是否决定处理的判断。 便于 disptacher 进行优先级阻断。校验通过会自动处理事件。"""
        if not self.is_valid:
            return False

        status, tmp_session = await self._pre_process(event)
        if status:
            self.logger.debug(
                f"event {event:hexid} 在 handler {self:hexid} pre_process 通过，处理方法为：{self.executor.__qualname__}"
            )
        if not status:
            return False

        if not self.temp:
            asyncio.create_task(self._run(event, tmp_session))
            return True

        async with self._run_lock:
            if self.is_valid:
                asyncio.create_task(self._run(event, tmp_session))
                self.is_valid = False
                return True
            else:
                return False


class AllEventHandler(EventHandler):
    def __init__(
        self,
        executor: Callable[[], Coroutine[Any, Any, None]],
        plugin: Any,
        logger: "BotLogger",
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        set_block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = True,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine]] = None,
    ) -> None:
        super().__init__(
            executor,
            plugin,
            logger,
            checker,
            priority,
            set_block,
            temp,
            session_rule,
            session_hold,
            direct_rouse,
            conflict_wait,
            conflict_cb,
        )


class MsgEventHandler(EventHandler):
    def __init__(
        self,
        executor: Callable[[], Coroutine[Any, Any, None]],
        plugin: Any,
        logger: "BotLogger",
        matcher: Optional["BotMatcher"] = None,
        parser: Optional["BotParser"] = None,
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        set_block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = True,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine]] = None,
    ) -> None:
        super().__init__(
            executor,
            plugin,
            logger,
            checker,
            priority,
            set_block,
            temp,
            session_rule,
            session_hold,
            direct_rouse,
            conflict_wait,
            conflict_cb,
        )
        self.matcher = matcher
        self.parser = parser

        # matcher 和 parser 不能同时存在
        if self.matcher and self.parser:
            raise BotValueError("参数 matcher 和 parser 不能同时存在")

    async def _pre_process(self, event: "MessageEvent") -> tuple[bool, "BotSession"]:  # type: ignore
        session = BotSessionManager.make_temp(event)
        if self.matcher is not None:
            return (
                await self._run_on_ctx(self.matcher.match(event.text), session),
                session,
            )

        if self.parser is not None:
            args = await self._run_on_ctx(self.parser.parse(event.text), session)
            if args is None:
                return False, session
            else:
                BotSessionManager.fill_args(session, args)

        return await self._run_on_ctx(self._verify(), session), session


class ReqEventHandler(EventHandler):
    def __init__(
        self,
        executor: Callable[[], Coroutine[Any, Any, None]],
        plugin: Any,
        logger: "BotLogger",
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        set_block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = True,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine]] = None,
    ) -> None:
        super().__init__(
            executor,
            plugin,
            logger,
            checker,
            priority,
            set_block,
            temp,
            session_rule,
            session_hold,
            direct_rouse,
            conflict_wait,
            conflict_cb,
        )


class NoticeEventHandler(EventHandler):
    def __init__(
        self,
        executor: Callable[[], Coroutine[Any, Any, None]],
        plugin: Any,
        logger: "BotLogger",
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        set_block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = True,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine]] = None,
    ) -> None:
        super().__init__(
            executor,
            plugin,
            logger,
            checker,
            priority,
            set_block,
            temp,
            session_rule,
            session_hold,
            direct_rouse,
            conflict_wait,
            conflict_cb,
        )


class MetaEventHandler(EventHandler):
    def __init__(
        self,
        executor: Callable[[], Coroutine[Any, Any, None]],
        plugin: Any,
        logger: "BotLogger",
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        set_block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = True,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine]] = None,
    ) -> None:
        super().__init__(
            executor,
            plugin,
            logger,
            checker,
            priority,
            set_block,
            temp,
            session_rule,
            session_hold,
            direct_rouse,
            conflict_wait,
            conflict_cb,
        )


EVENT_HANDLER_MAP: dict[str, tuple[Type[EventHandler], ...]] = {
    "message": (MsgEventHandler, AllEventHandler),
    "request": (ReqEventHandler, AllEventHandler),
    "notice": (NoticeEventHandler, AllEventHandler),
    "meta": (MetaEventHandler, AllEventHandler),
}
