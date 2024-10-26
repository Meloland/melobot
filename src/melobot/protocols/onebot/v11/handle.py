from functools import wraps
from typing import Callable, cast

from melobot.ctx import Context
from melobot.di import Depends, inject_deps
from melobot.handle import Flow, get_event, no_deps_node
from melobot.typ import AsyncCallable, HandleLevel, LogicMode, deprecated
from melobot.utils import singleton

from .adapter.event import Event, MessageEvent, MetaEvent, NoticeEvent, RequestEvent
from .utils import check, match
from .utils.abc import Checker, Matcher, ParseArgs, Parser
from .utils.parse import CmdArgFormatter, CmdParser


@singleton
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


@deprecated(
    "将于 melobot v3.0.0 移除，使用 melobot.protocols.onebot.v11.handle.GetParseArgs 代替"
)
def Args() -> ParseArgs:  # pylint: disable=invalid-name
    """获取解析参数，与 :func:`~.v11.handle.GetParseArgs` 等价

    已弃用。将于 `v3.0.0` 移除，使用 :func:`~.v11.handle.GetParseArgs` 代替

    :return: 解析参数
    """
    return cast(ParseArgs, Depends(ParseArgsCtx().get, recursive=False))


FlowDecorator = Callable[[AsyncCallable[..., bool | None]], Flow]


def on_event(
    checker: Checker | None | Callable[[Event], bool] = None,
    matcher: Matcher | None = None,
    parser: Parser | None = None,
    priority: HandleLevel = HandleLevel.NORMAL,
    block: bool = False,
    temp: bool = False,
) -> FlowDecorator:

    def flow_getter(func: AsyncCallable[..., bool | None]) -> Flow:
        if not isinstance(checker, Checker) and callable(checker):
            _checker = Checker.new(checker)
        else:
            _checker = cast(Checker, checker)

        func = inject_deps(func)

        @wraps(func)
        async def _node() -> bool | None:
            event = cast(Event, get_event())
            status = await _checker.check(event)
            if not status:
                return None

            p_args: ParseArgs | None = None
            if isinstance(event, MessageEvent):
                if matcher:
                    status = await matcher.match(event.text)
                    if not status:
                        return None

                if parser:
                    parse_args = await parser.parse(event.text)
                    if parse_args is None:
                        return None
                    p_args = parse_args

            event.spread = not block
            with ParseArgsCtx().in_ctx(p_args):
                return await func()

        n = no_deps_node(_node)
        n.name = func.__name__ if hasattr(func, "__name__") else "<anonymous callable>"
        return Flow(
            f"OneBotV11Flow[{n.name}]",
            [n],
            priority=priority,
            temp=temp,
        )

    return flow_getter


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
    priority: HandleLevel = HandleLevel.NORMAL,
    block: bool = False,
    temp: bool = False,
) -> FlowDecorator:
    return on_event(
        _checker_join(lambda e: e.is_message(), checker),  # type: ignore[arg-type]
        matcher,
        parser,
        priority,
        block,
        temp,
    )


def on_at_qq(
    qid: int | None = None,
    checker: Checker | None | Callable[[MessageEvent], bool] = None,
    matcher: Matcher | None = None,
    parser: Parser | None = None,
    priority: HandleLevel = HandleLevel.NORMAL,
    block: bool = False,
    temp: bool = False,
) -> FlowDecorator:
    return on_message(
        _checker_join(check.AtMsgChecker(qid if qid else "all"), checker),  # type: ignore[arg-type]
        matcher,
        parser,
        priority,
        block,
        temp,
    )


def on_command(
    cmd_start: str | list[str],
    cmd_sep: str | list[str],
    targets: str | list[str],
    fmtters: list[CmdArgFormatter | None] | None = None,
    checker: Checker | None | Callable[[MessageEvent], bool] = None,
    matcher: Matcher | None = None,
    priority: HandleLevel = HandleLevel.NORMAL,
    block: bool = False,
    temp: bool = False,
) -> FlowDecorator:
    return on_message(
        checker,
        matcher,
        CmdParser(cmd_start=cmd_start, cmd_sep=cmd_sep, targets=targets, fmtters=fmtters),
        priority,
        block,
        temp,
    )


def on_start_match(
    target: str | list[str],
    logic_mode: LogicMode = LogicMode.OR,
    checker: Checker | Callable[[MessageEvent], bool] | None = None,
    parser: Parser | None = None,
    priority: HandleLevel = HandleLevel.NORMAL,
    block: bool = False,
    temp: bool = False,
) -> FlowDecorator:
    return on_message(
        checker, match.StartMatcher(target, logic_mode), parser, priority, block, temp
    )


def on_contain_match(
    target: str | list[str],
    logic_mode: LogicMode = LogicMode.OR,
    checker: Checker | Callable[[MessageEvent], bool] | None = None,
    parser: Parser | None = None,
    priority: HandleLevel = HandleLevel.NORMAL,
    block: bool = False,
    temp: bool = False,
) -> FlowDecorator:
    return on_message(
        checker, match.ContainMatcher(target, logic_mode), parser, priority, block, temp
    )


def on_full_match(
    target: str | list[str],
    logic_mode: LogicMode = LogicMode.OR,
    checker: Checker | Callable[[MessageEvent], bool] | None = None,
    parser: Parser | None = None,
    priority: HandleLevel = HandleLevel.NORMAL,
    block: bool = False,
    temp: bool = False,
) -> FlowDecorator:
    return on_message(
        checker, match.FullMatcher(target, logic_mode), parser, priority, block, temp
    )


def on_end_match(
    target: str | list[str],
    logic_mode: LogicMode = LogicMode.OR,
    checker: Checker | Callable[[MessageEvent], bool] | None = None,
    parser: Parser | None = None,
    priority: HandleLevel = HandleLevel.NORMAL,
    block: bool = False,
    temp: bool = False,
) -> FlowDecorator:
    return on_message(
        checker, match.EndMatcher(target, logic_mode), parser, priority, block, temp
    )


def on_regex_match(
    target: str,
    logic_mode: LogicMode = LogicMode.OR,
    checker: Checker | Callable[[MessageEvent], bool] | None = None,
    parser: Parser | None = None,
    priority: HandleLevel = HandleLevel.NORMAL,
    block: bool = False,
    temp: bool = False,
) -> FlowDecorator:
    return on_message(
        checker, match.RegexMatcher(target, logic_mode), parser, priority, block, temp
    )


def on_request(
    checker: Checker | None | Callable[[RequestEvent], bool] = None,
    matcher: Matcher | None = None,
    parser: Parser | None = None,
    priority: HandleLevel = HandleLevel.NORMAL,
    block: bool = False,
    temp: bool = False,
) -> FlowDecorator:
    return on_event(
        _checker_join(lambda e: e.is_request(), checker),  # type: ignore[arg-type]
        matcher,
        parser,
        priority,
        block,
        temp,
    )


def on_notice(
    checker: Checker | None | Callable[[NoticeEvent], bool] = None,
    matcher: Matcher | None = None,
    parser: Parser | None = None,
    priority: HandleLevel = HandleLevel.NORMAL,
    block: bool = False,
    temp: bool = False,
) -> FlowDecorator:
    return on_event(
        _checker_join(lambda e: e.is_notice(), checker),  # type: ignore[arg-type]
        matcher,
        parser,
        priority,
        block,
        temp,
    )


def on_meta(
    checker: Checker | None | Callable[[MetaEvent], bool] = None,
    matcher: Matcher | None = None,
    parser: Parser | None = None,
    priority: HandleLevel = HandleLevel.NORMAL,
    block: bool = False,
    temp: bool = False,
) -> FlowDecorator:
    return on_event(
        _checker_join(lambda e: e.is_meta(), checker),  # type: ignore[arg-type]
        matcher,
        parser,
        priority,
        block,
        temp,
    )
