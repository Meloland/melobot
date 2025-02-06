from typing_extensions import Any, Callable, Sequence, cast

from melobot.adapter.model import Event as RootEvent
from melobot.handle import FlowDecorator
from melobot.handle import on_event as on_root_event
from melobot.handle import on_text
from melobot.session import Rule
from melobot.utils.check import Checker, checker_join
from melobot.utils.common import DeprecatedLoader as _DeprecatedLoader
from melobot.utils.match import Matcher
from melobot.utils.parse import Parser

from .adapter.event import Event, MessageEvent, MetaEvent, NoticeEvent, RequestEvent
from .utils import check


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
    return on_root_event(
        checker=checker_join(lambda e: isinstance(e, Event), checker),
        matcher=matcher,
        parser=parser,
        priority=priority,
        block=block,
        temp=temp,
        decos=decos,
        rule=cast(Rule[RootEvent] | None, rule),
    )


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
    return on_text(
        checker_join(lambda e: isinstance(e, MessageEvent), checker),
        matcher,
        parser,
        priority,
        block,
        temp,
        decos,
        legacy_session,
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
        checker_join(check.AtMsgChecker(qid if qid else "all"), checker),  # type: ignore[arg-type]
        matcher,
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
        checker_join(lambda e: isinstance(e, RequestEvent), checker),  # type: ignore[arg-type]
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
        checker_join(lambda e: isinstance(e, NoticeEvent), checker),  # type: ignore[arg-type]
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
        checker_join(lambda e: isinstance(e, MetaEvent), checker),  # type: ignore[arg-type]
        matcher,
        parser,
        priority,
        block,
        temp,
        decos,
        rule,
    )


_LOADER = _DeprecatedLoader(
    __name__,
    {
        "GetParseArgs": ("melobot.handle", "GetParseArgs", "3.1.1"),
        "on_command": ("melobot.handle", "on_command", "3.1.1"),
        "on_start_match": ("melobot.handle", "on_start_match", "3.1.1"),
        "on_contain_match": ("melobot.handle", "on_contain_match", "3.1.1"),
        "on_full_match": ("melobot.handle", "on_full_match", "3.1.1"),
        "on_end_match": ("melobot.handle", "on_end_match", "3.1.1"),
        "on_regex_match": ("melobot.handle", "on_regex_match", "3.1.1"),
    },
)


def __getattr__(name: str) -> Any:
    return _LOADER.get(name)
