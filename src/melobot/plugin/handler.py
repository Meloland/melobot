import asyncio

from ..base.abc import BotParser
from ..base.exceptions import DirectRetSignal, EventHandlerError, get_better_exc
from ..base.tools import get_rich_str
from ..base.typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Optional,
    ParseArgs,
    PriorLevel,
    T,
    Type,
    Union,
    Void,
    cast,
)
from ..context.session import SESSION_LOCAL, BotSessionManager, any_event

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
        direct_rouse: bool = False,
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

        if session_rule is None:
            if session_hold or direct_rouse or conflict_wait or conflict_cb:
                raise EventHandlerError(
                    "使用 session_rule 参数后才能使用以下参数：session_hold， direct_rouse, \
                                      conflict_wait, conflict_callback"
                )

        if conflict_wait and conflict_cb:
            raise EventHandlerError(
                "参数 conflict_wait 为 True 时，冲突回调永远不会被调用"
            )

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
        """在指定 session 上下文中运行协程。异常将会抛出."""
        if session._handler is None:
            BotSessionManager.inject(session, self)
        try:
            s_token = SESSION_LOCAL._add_ctx(session)
            return await asyncio.wait_for(asyncio.create_task(coro), timeout=timeout)
        finally:
            SESSION_LOCAL._del_ctx(s_token)
            # 这里可能因 bot 停止运行，导致退出事件执行方法时 session 为挂起态。因此需要强制唤醒
            if session._hup_signal.is_set():
                BotSessionManager._rouse(session)

    async def _run(
        self, event: Union["MessageEvent", "RequestEvent", "MetaEvent", "NoticeEvent"]
    ) -> None:
        """获取 session 然后准备运行 executor."""
        try:
            session = None
            if not self._direct_rouse:
                res = await BotSessionManager.try_attach(event, self)
                if res:
                    return
            session = await BotSessionManager.get(event, self)
            # 如果因为冲突没有获得 session，且指定了冲突回调
            if session is None and self._conflict_cb:
                temp_session = BotSessionManager.make_temp(event)
                await self._run_on_ctx(self._conflict_cb(), temp_session)
            # 如果因为冲突没有获得 session，但没有冲突回调
            if session is None:
                return
            # 如果没有冲突，正常获得到了 session
            exec_coro = self.executor()
            self.logger.debug(f"event {id(event)} 准备在 session {id(session)} 中处理")
            await self._run_on_ctx(exec_coro, session)
        except DirectRetSignal:
            pass
        except Exception as e:
            executor_name = self.executor.__qualname__
            self.logger.error(
                f"插件 {self._plugin.__id__} 事件处理方法 {executor_name} 发生异常"
            )
            self.logger.error("异常点 event：\n" + get_rich_str(event.raw))
            self.logger.error("异常回溯栈：\n" + get_better_exc(e))
            self.logger.error("异常点局部变量：\n" + get_rich_str(locals()))
        finally:
            if session is None:
                return
            self.logger.debug(f"event {id(event)} 在 session {id(session)} 中运行完毕")
            BotSessionManager.recycle(session, alive=self._hold)

    async def _pre_process(
        self, event: Union["MessageEvent", "RequestEvent", "MetaEvent", "NoticeEvent"]
    ) -> bool:
        session = BotSessionManager.make_temp(event)
        status = await self._run_on_ctx(self._verify(), session)
        return status

    async def evoke(
        self, event: Union["MessageEvent", "RequestEvent", "MetaEvent", "NoticeEvent"]
    ) -> bool:
        """接收总线分发的事件的方法。返回是否决定处理的判断。 便于 disptacher 进行优先级阻断。校验通过会自动处理事件。"""
        if not self.is_valid:
            return False

        status = await self._pre_process(event)
        if status:
            self.logger.debug(
                f"event {id(event)} 在 handler {id(self)} pre_process 通过，处理方法为：{self.executor.__qualname__}"
            )
        if not status:
            return False

        if not self.temp:
            asyncio.create_task(self._run(event))
            return True

        async with self._run_lock:
            if self.is_valid:
                asyncio.create_task(self._run(event))
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
        checker: "BotChecker",
        priority: PriorLevel,
        set_block: bool,
        temp: bool,
        session_rule: "SessionRule",
        session_hold: bool,
        direct_rouse: bool,
        conflict_wait: bool,
        conflict_cb: Callable[[], Coroutine],
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
        direct_rouse: bool = False,
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
            raise EventHandlerError("参数 matcher 和 parser 不能同时存在")

    def _match(
        self, event: "MessageEvent"
    ) -> bool | tuple[bool, str | None, ParseArgs | None]:
        """检查是否匹配."""
        if self.matcher:
            return self.matcher.match(event.text)
        if self.parser:
            _ = event._get_args(self.parser.id)
            if _ is Void:
                args_group = self.parser.parse(event.text)
                event._store_args(self.parser.id, args_group)
            else:
                args_group = _
            res, cmd_name, args = self.parser.test(args_group)
            return res, cmd_name, args
        return True

    async def _format(self, cmd_name: str, args: ParseArgs) -> bool:
        """格式化。只有 parser 存在时需要."""
        self.parser = cast(BotParser, self.parser)
        if not self.parser.need_format:
            return True
        status = await self.parser.format(cmd_name, args)
        return status

    async def _pre_process(self, event: "MessageEvent") -> bool:  # type: ignore
        session = BotSessionManager.make_temp(event)
        # 先进行 match，match 不支持回调，因此可以直接同步运行，而且无需异步加锁
        match_res = self._match(event)
        if isinstance(match_res, bool):
            if not match_res:
                return False
        else:
            res, cmd_name, args = match_res
            if not res:
                return False

        async def wrapped_func() -> bool:
            if not (await self._verify()):
                return False
            if self.parser:
                if not (await self._format(cmd_name, args)):  # type: ignore
                    return False
            return True

        status = await self._run_on_ctx(wrapped_func(), session)
        return status


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
        direct_rouse: bool = False,
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
        direct_rouse: bool = False,
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
        direct_rouse: bool = False,
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
