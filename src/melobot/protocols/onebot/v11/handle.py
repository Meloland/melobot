from asyncio import Lock
from functools import partial, wraps

from typing_extensions import Callable, Sequence, cast

from melobot.ctx import Context
from melobot.di import Depends, inject_deps
from melobot.handle import Flow, get_event, no_deps_node
from melobot.session import Rule, enter_session
from melobot.typ import AsyncCallable, LogicMode
from melobot.utils import get_obj_name

from .adapter.event import Event, MessageEvent, MetaEvent, NoticeEvent, RequestEvent
from .utils import check, match
from .utils.abc import Checker, Matcher, ParseArgs, Parser
from .utils.parse import CmdArgFormatter, CmdParser


class ParseArgsCtx(Context[ParseArgs | None]):
    def __init__(self) -> None:
        super().__init__(
            "ONEBOT_V11_PARSE_ARGS", LookupError, "当前上下文中不存在解析参数"
        )


def GetParseArgs() -> ParseArgs:  # pylint: disable=invalid-name
    """获取解析参数

    :return: 解析参数
    """
    return cast(ParseArgs, Depends(ParseArgsCtx().get, recursive=False))


class DefaultRule(Rule[MessageEvent]):
    """传统的会话规则（只针对消息事件）

    两消息事件如果在同一发送渠道，且由同一人发送，则在同一会话中
    """

    async def compare(self, e1: MessageEvent, e2: MessageEvent) -> bool:
        return e1.scope == e2.scope


class FlowDecorator:
    def __init__(
        self,
        checker: Checker | None | Callable[[Event], bool] = None,
        matcher: Matcher | None = None,
        parser: Parser | None = None,
        priority: int = 0,
        block: bool = False,
        temp: bool = False,
        decos: Sequence[Callable[[Callable], Callable]] | None = None,
        rule: Rule[Event] | None = None,
    ) -> None:
        self.checker: Checker | None
        if callable(checker):
            self.checker = Checker.new(checker)
        else:
            self.checker = checker

        self.matcher = matcher
        self.parser = parser
        self.priority = priority
        self.block = block
        self.decos = decos
        self.rule = rule

        self._temp = temp
        self._invalid = False
        self._lock = Lock()
        self._flow: Flow

    async def _pre_process(self, event: Event) -> tuple[bool, ParseArgs | None]:
        if self.checker:
            status = await self.checker.check(event)
            if not status:
                return (False, None)

        args: ParseArgs | None = None
        if isinstance(event, MessageEvent):
            if self.matcher:
                status = await self.matcher.match(event.text)
                if not status:
                    return (False, None)

            if self.parser:
                args = await self.parser.parse(event.text)
                if args:
                    return (True, args)
                return (False, None)

        return (True, None)

    async def _process(
        self, func: AsyncCallable[..., bool | None], event: Event, args: ParseArgs | None
    ) -> bool | None:
        event.spread = not self.block
        with ParseArgsCtx().unfold(args):
            if self.rule is not None:
                async with enter_session(self.rule):
                    return await func()
            return await func()

    async def ob11_flow_wrapped(
        self, func: AsyncCallable[..., bool | None]
    ) -> bool | None:
        if self._invalid:
            self._flow.dismiss()
            return None

        event = cast(Event, get_event())
        if not self._temp:
            passed, args = await self._pre_process(event)
            if not passed:
                return None
            return await self._process(func, event, args)

        async with self._lock:
            if self._invalid:
                self._flow.dismiss()
                return None

            passed, args = await self._pre_process(event)
            if not passed:
                return None
            self._invalid = True

        return await self._process(func, event, args)

    def __call__(self, func: AsyncCallable[..., bool | None]) -> Flow:
        func = inject_deps(func)
        if self.decos is not None:
            for deco in reversed(self.decos):
                func = deco(func)

        n = no_deps_node(wraps(func)(partial(self.ob11_flow_wrapped, func)))
        n.name = get_obj_name(func, otype="callable")
        self._flow = Flow(f"OneBotV11Flow[{n.name}]", (n,), priority=self.priority)
        return self._flow


def on_event(
    checker: Checker | None | Callable[[Event], bool] = None,
    matcher: Matcher | None = None,
    parser: Parser | None = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    rule: Rule[Event] | None = None,
) -> FlowDecorator:
    return FlowDecorator(checker, matcher, parser, priority, block, temp, decos, rule)


def _checker_join(*checkers: Checker | None | Callable[[Event], bool]) -> Checker:
    checker: Checker | None = None
    for c in checkers:
        if c is None:
            continue
        if isinstance(c, Checker):
            checker = checker & c if checker else c
        else:
            checker = checker & Checker.new(c) if checker else Checker.new(c)

    if checker is None:
        raise ValueError("检查器序列不能全为空")
    return checker


def on_message(
    checker: Checker | None | Callable[[MessageEvent], bool] = None,
    matcher: Matcher | None = None,
    parser: Parser | None = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    legacy_session: bool = False,
) -> FlowDecorator:
    if legacy_session:
        rule = DefaultRule()
    else:
        rule = None

    return on_event(
        _checker_join(lambda e: e.is_message(), checker),  # type: ignore[arg-type]
        matcher,
        parser,
        priority,
        block,
        temp,
        decos,
        cast(Rule[Event], rule),
    )


def on_at_qq(
    qid: int | None = None,
    checker: Checker | None | Callable[[MessageEvent], bool] = None,
    matcher: Matcher | None = None,
    parser: Parser | None = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    legacy_session: bool = False,
) -> FlowDecorator:
    return on_message(
        _checker_join(check.AtMsgChecker(qid if qid else "all"), checker),  # type: ignore[arg-type]
        matcher,
        parser,
        priority,
        block,
        temp,
        decos,
        legacy_session,
    )


def on_command(
    cmd_start: str | list[str],
    cmd_sep: str | list[str],
    targets: str | list[str],
    fmtters: list[CmdArgFormatter | None] | None = None,
    checker: Checker | None | Callable[[MessageEvent], bool] = None,
    matcher: Matcher | None = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    legacy_session: bool = False,
) -> FlowDecorator:
    return on_message(
        checker,
        matcher,
        CmdParser(cmd_start=cmd_start, cmd_sep=cmd_sep, targets=targets, fmtters=fmtters),
        priority,
        block,
        temp,
        decos,
        legacy_session,
    )


def on_start_match(
    target: str | list[str],
    logic_mode: LogicMode = LogicMode.OR,
    checker: Checker | Callable[[MessageEvent], bool] | None = None,
    parser: Parser | None = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    legacy_session: bool = False,
) -> FlowDecorator:
    return on_message(
        checker,
        match.StartMatcher(target, logic_mode),
        parser,
        priority,
        block,
        temp,
        decos,
        legacy_session,
    )


def on_contain_match(
    target: str | list[str],
    logic_mode: LogicMode = LogicMode.OR,
    checker: Checker | Callable[[MessageEvent], bool] | None = None,
    parser: Parser | None = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    legacy_session: bool = False,
) -> FlowDecorator:
    return on_message(
        checker,
        match.ContainMatcher(target, logic_mode),
        parser,
        priority,
        block,
        temp,
        decos,
        legacy_session,
    )


def on_full_match(
    target: str | list[str],
    logic_mode: LogicMode = LogicMode.OR,
    checker: Checker | Callable[[MessageEvent], bool] | None = None,
    parser: Parser | None = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    legacy_session: bool = False,
) -> FlowDecorator:
    return on_message(
        checker,
        match.FullMatcher(target, logic_mode),
        parser,
        priority,
        block,
        temp,
        decos,
        legacy_session,
    )


def on_end_match(
    target: str | list[str],
    logic_mode: LogicMode = LogicMode.OR,
    checker: Checker | Callable[[MessageEvent], bool] | None = None,
    parser: Parser | None = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    legacy_session: bool = False,
) -> FlowDecorator:
    return on_message(
        checker,
        match.EndMatcher(target, logic_mode),
        parser,
        priority,
        block,
        temp,
        decos,
        legacy_session,
    )


def on_regex_match(
    target: str,
    logic_mode: LogicMode = LogicMode.OR,
    checker: Checker | Callable[[MessageEvent], bool] | None = None,
    parser: Parser | None = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    legacy_session: bool = False,
) -> FlowDecorator:
    return on_message(
        checker,
        match.RegexMatcher(target, logic_mode),
        parser,
        priority,
        block,
        temp,
        decos,
        legacy_session,
    )


def on_request(
    checker: Checker | None | Callable[[RequestEvent], bool] = None,
    matcher: Matcher | None = None,
    parser: Parser | None = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    rule: Rule[Event] | None = None,
) -> FlowDecorator:
    return on_event(
        _checker_join(lambda e: e.is_request(), checker),  # type: ignore[arg-type]
        matcher,
        parser,
        priority,
        block,
        temp,
        decos,
        rule,
    )


def on_notice(
    checker: Checker | None | Callable[[NoticeEvent], bool] = None,
    matcher: Matcher | None = None,
    parser: Parser | None = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    rule: Rule[Event] | None = None,
) -> FlowDecorator:
    return on_event(
        _checker_join(lambda e: e.is_notice(), checker),  # type: ignore[arg-type]
        matcher,
        parser,
        priority,
        block,
        temp,
        decos,
        rule,
    )


def on_meta(
    checker: Checker | None | Callable[[MetaEvent], bool] = None,
    matcher: Matcher | None = None,
    parser: Parser | None = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    rule: Rule[Event] | None = None,
) -> FlowDecorator:
    return on_event(
        _checker_join(lambda e: e.is_meta(), checker),  # type: ignore[arg-type]
        matcher,
        parser,
        priority,
        block,
        temp,
        decos,
        rule,
    )
