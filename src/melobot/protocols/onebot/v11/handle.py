from typing_extensions import Callable, Sequence

from melobot.handle import FlowDecorator
from melobot.session import DefaultRule, Rule
from melobot.typ import SyncOrAsyncCallable
from melobot.utils.check import Checker, checker_join
from melobot.utils.match import Matcher
from melobot.utils.parse import Parser

from .adapter.event import (
    DownstreamCallEvent,
    Event,
    MessageEvent,
    MetaEvent,
    NoticeEvent,
    RequestEvent,
    UpstreamRetEvent,
)
from .utils import check


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


def on_message(
    checker: Checker | None | SyncOrAsyncCallable[[MessageEvent], bool] = None,
    matcher: Matcher | None = None,
    parser: Parser | None = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    legacy_session: bool = False,
) -> FlowDecorator:
    return FlowDecorator(
        checker=checker_join(lambda e: isinstance(e, MessageEvent), checker),  # type: ignore[arg-type]
        matcher=matcher,
        parser=parser,
        priority=priority,
        block=block,
        temp=temp,
        decos=decos,
        rule=DefaultRule() if legacy_session else None,
    )


def on_at_qq(
    qid: int | None = None,
    checker: Checker | None | SyncOrAsyncCallable[[MessageEvent], bool] = None,
    matcher: Matcher | None = None,
    parser: Parser | None = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    legacy_session: bool = False,
) -> FlowDecorator:
    _checker = check.AtMsgChecker(qid if qid is not None else "all")
    return FlowDecorator(
        checker=checker_join(lambda e: isinstance(e, Event), _checker, checker),  # type: ignore[arg-type]
        matcher=matcher,
        parser=parser,
        priority=priority,
        block=block,
        temp=temp,
        decos=decos,
        rule=DefaultRule() if legacy_session else None,
    )


def on_request(
    checker: Checker | None | SyncOrAsyncCallable[[RequestEvent], bool] = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    rule: Rule[Event] | None = None,
) -> FlowDecorator:
    return FlowDecorator(
        checker=checker_join(lambda e: isinstance(e, RequestEvent), checker),  # type: ignore[arg-type]
        priority=priority,
        block=block,
        temp=temp,
        decos=decos,
        rule=rule,  # type: ignore[arg-type]
    )


def on_notice(
    checker: Checker | None | SyncOrAsyncCallable[[NoticeEvent], bool] = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    rule: Rule[Event] | None = None,
) -> FlowDecorator:
    return FlowDecorator(
        checker=checker_join(lambda e: isinstance(e, NoticeEvent), checker),  # type: ignore[arg-type]
        priority=priority,
        block=block,
        temp=temp,
        decos=decos,
        rule=rule,  # type: ignore[arg-type]
    )


def on_meta(
    checker: Checker | None | SyncOrAsyncCallable[[MetaEvent], bool] = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    rule: Rule[Event] | None = None,
) -> FlowDecorator:
    return FlowDecorator(
        checker=checker_join(lambda e: isinstance(e, MetaEvent), checker),  # type: ignore[arg-type]
        priority=priority,
        block=block,
        temp=temp,
        decos=decos,
        rule=rule,  # type: ignore[arg-type]
    )


def on_downstream_call(
    checker: Checker | None | SyncOrAsyncCallable[[DownstreamCallEvent], bool] = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    rule: Rule[Event] | None = None,
) -> FlowDecorator:
    return FlowDecorator(
        checker=checker_join(lambda e: isinstance(e, DownstreamCallEvent), checker),  # type: ignore[arg-type]
        priority=priority,
        block=block,
        temp=temp,
        decos=decos,
        rule=rule,  # type: ignore[arg-type]
    )


def on_upstream_ret(
    checker: Checker | None | SyncOrAsyncCallable[[UpstreamRetEvent], bool] = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    rule: Rule[Event] | None = None,
) -> FlowDecorator:
    return FlowDecorator(
        checker=checker_join(lambda e: isinstance(e, UpstreamRetEvent), checker),  # type: ignore[arg-type]
        priority=priority,
        block=block,
        temp=temp,
        decos=decos,
        rule=rule,  # type: ignore[arg-type]
    )
