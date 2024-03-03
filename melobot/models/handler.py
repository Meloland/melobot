import asyncio as aio
import traceback

from ..types.core import IActionResponder
from ..types.exceptions import *
from ..types.models import BotEvent, SessionRule
from ..types.typing import *
from ..types.utils import BotChecker, BotMatcher, BotParser, Logger
from .action import msg_action
from .event import MsgEvent
from .session import SESSION_LOCAL, BotSession, BotSessionManager


class EventHandler:
    def __init__(
        self,
        executor: AsyncFunc[None],
        plugin: Any,
        responder: IActionResponder,
        logger: Logger,
        checker: BotChecker,
        priority: PriorityLevel,
        timeout: float,
        set_block: bool,
        temp: bool,
        session_rule: SessionRule,
        session_hold: bool,
        direct_rouse: bool,
        conflict_wait: bool,
        conflict_cb_maker: Callable[[None], Coroutine],
        overtime_cb_maker: Callable[[None], Coroutine],
    ) -> None:
        super().__init__()
        self.is_valid = True

        self.executor = executor
        self.responder = responder
        self.logger = logger
        self.checker = checker
        self.priority = priority
        self.timeout = timeout
        self.set_block = set_block
        self.temp = temp

        self._run_lock = aio.Lock()
        self._rule = session_rule
        self._hold = session_hold
        self._plugin = plugin
        self._direct_rouse = direct_rouse
        self._conflict_cb_maker = conflict_cb_maker
        self._overtime_cb_maker = overtime_cb_maker
        self._wait_flag = conflict_wait

        if session_rule is None:
            if session_hold or direct_rouse or conflict_wait or conflict_cb_maker:
                raise BotRuntimeError(
                    "使用 session_rule 参数后才能使用以下参数：session_hold， direct_rouse, \
                                      conflict_wait, conflict_callback"
                )

        if conflict_wait and conflict_cb_maker:
            raise BotRuntimeError(
                "参数 conflict_wait 为 True 时，冲突回调永远不会被调用"
            )

    def _invalidate(self) -> None:
        """
        标记此 handler 为无效状态
        """
        self.is_valid = False

    def _verify(self, event: BotEvent) -> bool:
        """
        验证事件是否有触发执行的资格（验权）
        """
        if self.checker:
            return self.checker.check(event)
        return True

    async def _run_on_ctx(
        self, coro: Coroutine, session: BotSession = None, timeout: float = None
    ) -> None:
        """
        在指定 session 上下文中运行协程。异常将会抛出
        """
        if session._handler is None:
            BotSessionManager.inject(session, self)
        try:
            s_token = SESSION_LOCAL._add_ctx(session)
            await aio.wait_for(aio.create_task(coro), timeout=timeout)
        finally:
            SESSION_LOCAL._del_ctx(s_token)
            # 这里可能因 bot 停止运行，导致退出事件执行方法时 session 为挂起态。因此需要强制唤醒
            if session._hup_signal.is_set():
                BotSessionManager._rouse(session)

    async def _run(self, event: MsgEvent) -> None:
        """
        获取 session 然后准备运行 executor
        """
        try:
            session = None
            if not self._direct_rouse:
                res = await BotSessionManager.try_attach(event, self)
                if res:
                    return
            session = await BotSessionManager.get(event, self.responder, self)
            # 如果因为冲突没有获得 session，且指定了冲突回调
            if session is None and self._conflict_cb_maker:
                temp_session = BotSessionManager.make_temp(event, self.responder)
                await self._run_on_ctx(self._conflict_cb_maker(), temp_session)
            # 如果因为冲突没有获得 session，但没有冲突回调
            if session is None:
                return
            # 如果没有冲突，正常获得到了 session
            try:
                exec_coro = self.executor(self._plugin)
                await self._run_on_ctx(exec_coro, session, self.timeout)
            except aio.TimeoutError:
                if self._overtime_cb_maker:
                    await self._run_on_ctx(self._overtime_cb_maker(), session)
        except BotExecutorQuickExit:
            pass
        except Exception as e:
            e_name = e.__class__.__name__
            executor_name = self.executor.__qualname__
            self.logger.error(
                f"插件 {self._plugin.__class__.__id__} 事件处理方法 {executor_name} 发生异常：[{e_name}] {e}"
            )
            self.logger.debug(f"异常点的事件记录为：{event.raw}")
            self.logger.debug("异常回溯栈：\n" + traceback.format_exc().strip("\n"))
        finally:
            if session is None:
                return
            BotSessionManager.recycle(session, alive=self._hold)

    async def evoke(self, event: MsgEvent) -> bool:
        """
        接收总线分发的事件的方法。返回是否决定处理的判断。
        便于 disptacher 进行优先级阻断。校验通过会自动处理事件。
        """
        if not self._verify(event):
            return False

        if self._direct_rouse:
            res = await BotSessionManager.try_attach(event, self)
            if res:
                return True

        if not self.is_valid:
            return False

        if not self.temp:
            aio.create_task(self._run(event))
            return True

        async with self._run_lock:
            if self.is_valid:
                aio.create_task(self._run(event))
                self._invalidate()
                return True
            else:
                return False


class MsgEventHandler(EventHandler):
    def __init__(
        self,
        executor: AsyncFunc[None],
        plugin: Any,
        responder: IActionResponder,
        logger: Logger,
        matcher: BotMatcher = None,
        parser: BotParser = None,
        checker: BotChecker = None,
        priority: PriorityLevel = PriorityLevel.MEAN,
        timeout: float = None,
        set_block: bool = False,
        temp: bool = False,
        session_rule: SessionRule = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb_maker: Callable[[None], Coroutine] = None,
        overtime_cb_maker: Callable[[None], Coroutine] = None,
    ) -> None:
        super().__init__(
            executor,
            plugin,
            responder,
            logger,
            checker,
            priority,
            timeout,
            set_block,
            temp,
            session_rule,
            session_hold,
            direct_rouse,
            conflict_wait,
            conflict_cb_maker,
            overtime_cb_maker,
        )
        self.matcher = matcher
        self.parser = parser

        # matcher 和 parser 不能同时存在
        if self.matcher and self.parser:
            raise BotRuntimeError("参数 matcher 和 parser 不能同时存在")

    def _match_and_parse(self, event: MsgEvent) -> bool:
        """
        通过验权后，尝试对事件进行匹配。
        有普通的匹配器（matcher）匹配，也可以使用解析器（parser）匹配
        """
        if self.matcher:
            return self.matcher.match(event.text)
        if self.parser:
            args_group = event._get_args(self.parser.id)
            if args_group == -1:
                args_group = self.parser.parse(event.text)
                event._store_args(self.parser.id, args_group)
            res, cmd_name, args = self.parser.test(args_group)
            if not res:
                return False
            try:
                if self.parser.need_format:
                    self.parser.format(args)
                return True
            except BotFormatFailed as e:
                msg = f"命令 {cmd_name} 参数格式化失败：\n" + e.__str__()
                action = msg_action(
                    msg, event.is_private(), event.sender.id, event.group_id
                )
                aio.create_task(self.responder.take_action(action))
                return False
        return True

    async def evoke(self, event: MsgEvent) -> bool:
        """
        接收总线分发的事件的方法。返回是否决定处理的判断。
        便于 disptacher 进行优先级阻断。校验通过会自动处理事件。
        """
        if not self._verify(event):
            return False

        if self._direct_rouse:
            res = await BotSessionManager.try_attach(event, self)
            if res:
                return True

        if not self.is_valid:
            return False

        if not self._match_and_parse(event):
            return False

        if not self.temp:
            aio.create_task(self._run(event))
            return True

        async with self._run_lock:
            if self.is_valid:
                aio.create_task(self._run(event))
                self._invalidate()
                return True
            else:
                return False


class ReqEventHandler(EventHandler):
    def __init__(
        self,
        executor: AsyncFunc[None],
        plugin: Any,
        responder: IActionResponder,
        logger: Logger,
        checker: BotChecker = None,
        priority: PriorityLevel = PriorityLevel.MEAN,
        timeout: float = None,
        set_block: bool = False,
        temp: bool = False,
        session_rule: SessionRule = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb_maker: Callable[[None], Coroutine] = None,
        overtime_cb_maker: Callable[[None], Coroutine] = None,
    ) -> None:
        super().__init__(
            executor,
            plugin,
            responder,
            logger,
            checker,
            priority,
            timeout,
            set_block,
            temp,
            session_rule,
            session_hold,
            direct_rouse,
            conflict_wait,
            conflict_cb_maker,
            overtime_cb_maker,
        )


class NoticeEventHandler(EventHandler):
    def __init__(
        self,
        executor: AsyncFunc[None],
        plugin: Any,
        responder: IActionResponder,
        logger: Logger,
        checker: BotChecker = None,
        priority: PriorityLevel = PriorityLevel.MEAN,
        timeout: float = None,
        set_block: bool = False,
        temp: bool = False,
        session_rule: SessionRule = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb_maker: Callable[[None], Coroutine] = None,
        overtime_cb_maker: Callable[[None], Coroutine] = None,
    ) -> None:
        super().__init__(
            executor,
            plugin,
            responder,
            logger,
            checker,
            priority,
            timeout,
            set_block,
            temp,
            session_rule,
            session_hold,
            direct_rouse,
            conflict_wait,
            conflict_cb_maker,
            overtime_cb_maker,
        )


class MetaEventHandler(EventHandler):
    def __init__(
        self,
        executor: AsyncFunc[None],
        plugin: Any,
        responder: IActionResponder,
        logger: Logger,
        checker: BotChecker = None,
        priority: PriorityLevel = PriorityLevel.MEAN,
        timeout: float = None,
        set_block: bool = False,
        temp: bool = False,
        session_rule: SessionRule = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb_maker: Callable[[None], Coroutine] = None,
        overtime_cb_maker: Callable[[None], Coroutine] = None,
    ) -> None:
        super().__init__(
            executor,
            plugin,
            responder,
            logger,
            checker,
            priority,
            timeout,
            set_block,
            temp,
            session_rule,
            session_hold,
            direct_rouse,
            conflict_wait,
            conflict_cb_maker,
            overtime_cb_maker,
        )


# 事件方法（事件执行器）构造参数
EventHandlerArgs = NamedTuple(
    "EventHandlerArgs", executor=AsyncFunc[None], type=EventHandler, params=List[Any]
)
