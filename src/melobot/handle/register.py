from asyncio import Lock
from functools import partial, wraps

from typing_extensions import Callable, Sequence, cast

from ..adapter.model import Event, TextEvent
from ..ctx import Context, FlowCtx
from ..di import Depends, inject_deps
from ..session.base import enter_session
from ..session.option import DefaultRule, Rule
from ..typ._enum import LogicMode
from ..typ.base import AsyncCallable, SyncOrAsyncCallable
from ..utils.check import Checker, checker_join
from ..utils.common import get_obj_name
from ..utils.match import (
    ContainMatcher,
    EndMatcher,
    FullMatcher,
    Matcher,
    RegexMatcher,
    StartMatcher,
)
from ..utils.parse import AbstractParseArgs, CmdArgFormatter, CmdParser, Parser
from .base import Flow, no_deps_node


class ParseArgsCtx(Context[AbstractParseArgs | None]):
    def __init__(self) -> None:
        super().__init__("MELOBOT_PARSE_ARGS", LookupError, "当前上下文中不存在解析参数")


def GetParseArgs() -> AbstractParseArgs:  # pylint: disable=invalid-name
    """获取解析参数

    :return: 解析参数
    """
    return cast(AbstractParseArgs, Depends(ParseArgsCtx().get, recursive=False))


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

    async def _pre_process(self, event: Event) -> tuple[bool, AbstractParseArgs | None]:
        if self.checker:
            status = await self.checker.check(event)
            if not status:
                return (False, None)

        args: AbstractParseArgs | None = None
        if isinstance(event, TextEvent):
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
        self,
        func: AsyncCallable[..., bool | None],
        event: Event,
        args: AbstractParseArgs | None,
    ) -> bool | None:
        event.spread = not self.block
        with ParseArgsCtx().unfold(args):
            if self.rule is not None:
                async with enter_session(self.rule):
                    return await func()
            return await func()

    async def auto_flow_wrapped(
        self, func: AsyncCallable[..., bool | None]
    ) -> bool | None:
        if self._invalid:
            self._flow.dismiss()
            return None

        event = FlowCtx().get().completion.event
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

    def __call__(self, func: SyncOrAsyncCallable[..., bool | None]) -> Flow:
        func = inject_deps(func)
        if self.decos is not None:
            for deco in reversed(self.decos):
                func = deco(func)

        n = no_deps_node(wraps(func)(partial(self.auto_flow_wrapped, func)))
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


def on_text(
    checker: Checker | None | Callable[[TextEvent], bool] = None,
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
        checker_join(lambda e: isinstance(e, TextEvent), checker),  # type: ignore[arg-type]
        matcher,
        parser,
        priority,
        block,
        temp,
        decos,
        cast(Rule[Event] | None, rule),
    )


def on_command(
    cmd_start: str | list[str],
    cmd_sep: str | list[str],
    targets: str | list[str],
    fmtters: list[CmdArgFormatter | None] | None = None,
    checker: Checker | None | Callable[[TextEvent], bool] = None,
    matcher: Matcher | None = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    legacy_session: bool = False,
) -> FlowDecorator:
    return on_text(
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
    checker: Checker | Callable[[TextEvent], bool] | None = None,
    parser: Parser | None = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    legacy_session: bool = False,
) -> FlowDecorator:
    return on_text(
        checker,
        StartMatcher(target, logic_mode),
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
    checker: Checker | Callable[[TextEvent], bool] | None = None,
    parser: Parser | None = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    legacy_session: bool = False,
) -> FlowDecorator:
    return on_text(
        checker,
        ContainMatcher(target, logic_mode),
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
    checker: Checker | Callable[[TextEvent], bool] | None = None,
    parser: Parser | None = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    legacy_session: bool = False,
) -> FlowDecorator:
    return on_text(
        checker,
        FullMatcher(target, logic_mode),
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
    checker: Checker | Callable[[TextEvent], bool] | None = None,
    parser: Parser | None = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    legacy_session: bool = False,
) -> FlowDecorator:
    return on_text(
        checker,
        EndMatcher(target, logic_mode),
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
    checker: Checker | Callable[[TextEvent], bool] | None = None,
    parser: Parser | None = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    legacy_session: bool = False,
) -> FlowDecorator:
    return on_text(
        checker,
        RegexMatcher(target, logic_mode),
        parser,
        priority,
        block,
        temp,
        decos,
        legacy_session,
    )
