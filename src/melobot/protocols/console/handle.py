from typing_extensions import Callable, Sequence

from melobot.handle import FlowDecorator
from melobot.session import Rule
from melobot.typ import SyncOrAsyncCallable
from melobot.utils.check import Checker, checker_join
from melobot.utils.match import Matcher
from melobot.utils.parse import Parser

from .adapter.event import Event, StdinEvent


def on_event(
    checker: Checker | None | SyncOrAsyncCallable[[Event], bool] = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    rule: Rule[Event] | None = None,
) -> FlowDecorator:
    return FlowDecorator(
        checker=checker_join(lambda e: isinstance(e, Event), checker),  # type: ignore[arg-type]
        priority=priority,
        block=block,
        temp=temp,
        decos=decos,
        rule=rule,  # type: ignore[arg-type]
    )


def on_input(
    checker: Checker | None | SyncOrAsyncCallable[[StdinEvent], bool] = None,
    matcher: Matcher | None = None,
    parser: Parser | None = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    rule: Rule[Event] | None = None,
) -> FlowDecorator:
    return FlowDecorator(
        checker=checker_join(lambda e: isinstance(e, StdinEvent), checker),  # type: ignore[arg-type]
        matcher=matcher,
        parser=parser,
        priority=priority,
        block=block,
        temp=temp,
        decos=decos,
        rule=rule,  # type: ignore[arg-type]
    )
