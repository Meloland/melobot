import asyncio as aio
import traceback

from melobot.models.event import MessageEvent

from ..context.session import SESSION_LOCAL, BotSessionManager, any_event
from ..types.exceptions import *
from ..types.typing import *

if TYPE_CHECKING:
    from ..context.session import BotSession
    from ..models.event import MessageEvent
    from ..types.abc import (
        AbstractResponder,
        BotChecker,
        BotEvent,
        BotMatcher,
        BotParser,
        SessionRule,
    )
    from ..utils.logger import Logger


class EventHandler:
    def __init__(
        self,
        executor: Callable[[], Coroutine[Any, Any, None]],
        plugin: Any,
        responder: "AbstractResponder",
        logger: "Logger",
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
        super().__init__()
        self.is_valid = True

        self.executor = executor
        self.responder = responder
        self.logger = logger
        self.checker = checker
        self.priority = priority
        self.set_block = set_block
        self.temp = temp

        self._run_lock = aio.Lock()
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
        """
        验证事件是否有触发执行的资格（验权）
        """
        if self.checker:
            return await self.checker.check(any_event())
        return True

    async def _run_on_ctx(
        self,
        coro: Coroutine[Any, Any, T],
        session: "BotSession" = None,
        timeout: float = None,
    ) -> T:
        """
        在指定 session 上下文中运行协程。异常将会抛出
        """
        if session._handler is None:
            BotSessionManager.inject(session, self)
        try:
            s_token = SESSION_LOCAL._add_ctx(session)
            return await aio.wait_for(aio.create_task(coro), timeout=timeout)
        finally:
            SESSION_LOCAL._del_ctx(s_token)
            # 这里可能因 bot 停止运行，导致退出事件执行方法时 session 为挂起态。因此需要强制唤醒
            if session._hup_signal.is_set():
                BotSessionManager._rouse(session)

    async def _run(self, event: "BotEvent") -> None:
        """
        获取 session 然后准备运行 executor
        """
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
            exec_coro = self.executor(self._plugin)
            await self._run_on_ctx(exec_coro, session)
        except DirectRetSignal:
            pass
        except Exception as e:
            e_name = e.__class__.__name__
            executor_name = self.executor.__qualname__
            self.logger.error(
                f"插件 {self._plugin.ID} 事件处理方法 {executor_name} 发生异常：[{e_name}] {e}"
            )
            self.logger.debug(f"异常点的事件记录为：{event.raw}")
            self.logger.debug("异常回溯栈：\n" + traceback.format_exc().strip("\n"))
        finally:
            if session is None:
                return
            BotSessionManager.recycle(session, alive=self._hold)

    async def _pre_process(self, event: "BotEvent") -> Coroutine[Any, Any, bool]:
        session = BotSessionManager.make_temp(event)
        status = await self._run_on_ctx(self._verify(), session)
        return status

    async def evoke(self, event: "BotEvent") -> bool:
        """
        接收总线分发的事件的方法。返回是否决定处理的判断。
        便于 disptacher 进行优先级阻断。校验通过会自动处理事件。
        """
        if not self.is_valid:
            return False

        if not (await self._pre_process(event)):
            return False

        if not self.temp:
            aio.create_task(self._run(event))
            return True

        async with self._run_lock:
            if self.is_valid:
                aio.create_task(self._run(event))
                self.is_valid = False
                return True
            else:
                return False


class AllEventHandler(EventHandler):
    def __init__(
        self,
        executor: Callable[[], Coroutine[Any, Any, None]],
        plugin: Any,
        responder: "AbstractResponder",
        logger: "Logger",
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
            responder,
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
        responder: "AbstractResponder",
        logger: "Logger",
        matcher: "BotMatcher" = None,
        parser: "BotParser" = None,
        checker: "BotChecker" = None,
        priority: PriorLevel = PriorLevel.MEAN,
        set_block: bool = False,
        temp: bool = False,
        session_rule: "SessionRule" = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Callable[[], Coroutine] = None,
    ) -> None:
        super().__init__(
            executor,
            plugin,
            responder,
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
        """
        检查是否匹配
        """
        if self.matcher:
            return self.matcher.match(event.text)
        if self.parser:
            args_group = event._get_args(self.parser.id)
            if args_group == -1:
                args_group = self.parser.parse(event.text)
                event._store_args(self.parser.id, args_group)
            res, cmd_name, args = self.parser.test(args_group)
            return res, cmd_name, args
        return True

    async def _format(self, cmd_name: str, args: ParseArgs) -> bool:
        """
        格式化。只有 parser 存在时需要
        """
        if not self.parser.need_format:
            return True
        status = await self.parser.format(cmd_name, args)
        return status

    async def _pre_process(self, event: MessageEvent) -> Coroutine[Any, Any, bool]:
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
                if not (await self._format(cmd_name, args)):
                    return False
            return True

        status = await self._run_on_ctx(wrapped_func(), session)
        return status


class ReqEventHandler(EventHandler):
    def __init__(
        self,
        executor: Callable[[], Coroutine[Any, Any, None]],
        plugin: Any,
        responder: "AbstractResponder",
        logger: "Logger",
        checker: "BotChecker" = None,
        priority: PriorLevel = PriorLevel.MEAN,
        set_block: bool = False,
        temp: bool = False,
        session_rule: "SessionRule" = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Callable[[], Coroutine] = None,
    ) -> None:
        super().__init__(
            executor,
            plugin,
            responder,
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
        responder: "AbstractResponder",
        logger: "Logger",
        checker: "BotChecker" = None,
        priority: PriorLevel = PriorLevel.MEAN,
        set_block: bool = False,
        temp: bool = False,
        session_rule: "SessionRule" = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Callable[[], Coroutine] = None,
    ) -> None:
        super().__init__(
            executor,
            plugin,
            responder,
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
        responder: "AbstractResponder",
        logger: "Logger",
        checker: "BotChecker" = None,
        priority: PriorLevel = PriorLevel.MEAN,
        set_block: bool = False,
        temp: bool = False,
        session_rule: "SessionRule" = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Callable[[], Coroutine] = None,
    ) -> None:
        super().__init__(
            executor,
            plugin,
            responder,
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
