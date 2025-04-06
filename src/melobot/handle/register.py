from asyncio import Lock
from functools import partial, wraps

from typing_extensions import Any, Callable, Iterable, Sequence, cast

from ..adapter.model import Event, TextEvent
from ..ctx import FlowCtx, ParseArgsCtx
from ..di import inject_deps
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


class FlowDecorator:
    def __init__(
        self,
        checker: Checker | None | SyncOrAsyncCallable[[Event], bool] = None,
        matcher: Matcher | None = None,
        parser: Parser | None = None,
        priority: int = 0,
        block: bool = False,
        temp: bool = False,
        decos: Sequence[Callable[[Callable], Callable]] | None = None,
        rule: Rule[Event] | None = None,
    ) -> None:
        """处理流装饰器

        :param checker: 检查器
        :param matcher: 匹配器（指定匹配器，需要先验证已经是文本事件）
        :param parser: 解析器（指定解析器，需要先验证已经是文本事件）
        :param priority: 优先级
        :param block: 是否阻断向低优先级传播
        :param temp: 是否临时使用（处理一次事件后停用）
        :param decos: 装饰器组
        :param rule: 会话规则
        """
        self.checker: Checker | None
        if callable(checker):
            self.checker = Checker.new(checker)
        else:
            self.checker = checker

        self.matcher = matcher
        self.parser = parser

        self._priority = priority
        self._block = block
        self._decos = decos
        self._rule = rule

        self._temp = temp
        self._invalid = False
        self._lock = Lock()
        self._flow: Flow

    def __call__(self, func: SyncOrAsyncCallable[..., bool | None]) -> Flow:
        func = inject_deps(func)
        if self._decos is not None:
            for deco in reversed(self._decos):
                func = deco(func)

        n = no_deps_node(wraps(func)(partial(self._flow_wrapped, func)))
        n.name = get_obj_name(func, otype="callable")
        self._flow = Flow(
            f"OneBotV11Flow[{n.name}]", (n,), priority=self._priority, guard=self._guard
        )
        return self._flow

    async def _guard(self, event: Event) -> bool:
        if self.checker:
            status = await self.checker.check(event)
            if not status:
                return False

        if self.matcher:
            event = cast(TextEvent, event)
            status = await self.matcher.match(event.text)
            if not status:
                return False

        return True

    async def _flow_wrapped(self, func: AsyncCallable[..., bool | None]) -> bool | None:
        if self._invalid:
            self._flow.dismiss()
            return None

        event = FlowCtx().get().completion.event
        if not self._temp:
            passed, args = await self._parse(event)
            if not passed:
                return None
            return await self._process(func, event, args)

        async with self._lock:
            if self._invalid:
                self._flow.dismiss()
                return None

            passed, args = await self._parse(event)
            if not passed:
                return None
            self._invalid = True

        return await self._process(func, event, args)

    async def _process(
        self, func: AsyncCallable[..., bool | None], event: Event, args: AbstractParseArgs | None
    ) -> bool | None:
        event.spread = not self._block
        parse_args_ctx = ParseArgsCtx()
        if args is not None:
            args_token = parse_args_ctx.add(args)
        else:
            args_token = None

        try:
            if self._rule is not None:
                async with enter_session(self._rule):
                    return await func()
            return await func()
        finally:
            if args_token:
                parse_args_ctx.remove(args_token)

    async def _parse(self, event: Event) -> tuple[bool, AbstractParseArgs | None]:
        args: AbstractParseArgs | None = None
        if self.parser:
            event = cast(TextEvent, event)
            args = await self.parser.parse(event.text)
            if args:
                return (True, args)
            return (False, None)

        return (True, None)


def on_event(
    checker: Checker | None | SyncOrAsyncCallable[[Event], bool] = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    rule: Rule[Event] | None = None,
) -> FlowDecorator:
    """绑定任意事件的处理流装饰方法

    在前期的教程中，处理流装饰方法也称为绑定方法

    :param checker: 检查器
    :param priority: 优先级
    :param block: 是否阻断向低优先级传播
    :param temp: 是否临时使用（处理一次事件后停用）
    :param decos: 装饰器组
    :param rule: 会话规则
    :return: 处理流装饰器
    """
    return FlowDecorator(checker, None, None, priority, block, temp, decos, rule)


def on_text(
    checker: Checker | None | SyncOrAsyncCallable[[TextEvent], bool] = None,
    matcher: Matcher | None = None,
    parser: Parser | None = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    legacy_session: bool = False,
) -> FlowDecorator:
    """绑定文本事件的处理流装饰方法

    在前期的教程中，处理流装饰方法也称为绑定方法

    :param checker: 检查器
    :param matcher: 匹配器
    :param parser: 解析器
    :param priority: 优先级
    :param block: 是否阻断向低优先级传播
    :param temp: 是否临时使用（处理一次事件后停用）
    :param decos: 装饰器组
    :param legacy_session: 是否自动启用传统会话
    :return: 处理流装饰器
    """

    return FlowDecorator(
        checker_join(lambda e: isinstance(e, TextEvent), checker),  # type: ignore[arg-type]
        matcher,
        parser,
        priority,
        block,
        temp,
        decos,
        DefaultRule() if legacy_session else None,
    )


def on_command(
    cmd_start: str | Iterable[str],
    cmd_sep: str | Iterable[str],
    targets: str | Sequence[str],
    fmtters: Sequence[CmdArgFormatter | None] | None = None,
    checker: Checker | None | SyncOrAsyncCallable[[TextEvent], bool] = None,
    matcher: Matcher | None = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    legacy_session: bool = False,
) -> FlowDecorator:
    """绑定文本事件的“命令解析”处理流装饰方法

    在前期的教程中，处理流装饰方法也称为绑定方法

    :param cmd_start: 命令起始符
    :param cmd_sep: 命令分隔符
    :param targets: 解析匹配的命令名
    :param fmtters: 命令参数格式化器
    :param checker: 检查器
    :param matcher: 匹配器
    :param priority: 优先级
    :param block: 是否阻断向低优先级传播
    :param temp: 是否临时使用（处理一次事件后停用）
    :param decos: 装饰器组
    :param legacy_session: 是否自动启用传统会话
    :return: 处理流装饰器
    """
    return FlowDecorator(
        checker_join(lambda e: isinstance(e, TextEvent), checker),  # type: ignore[arg-type]
        matcher,
        CmdParser(cmd_start=cmd_start, cmd_sep=cmd_sep, targets=targets, fmtters=fmtters),
        priority,
        block,
        temp,
        decos,
        DefaultRule() if legacy_session else None,
    )


def on_start_match(
    target: str | Sequence[str],
    logic_mode: LogicMode = LogicMode.OR,
    checker: Checker | SyncOrAsyncCallable[[TextEvent], bool] | None = None,
    parser: Parser | None = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    legacy_session: bool = False,
) -> FlowDecorator:
    """绑定文本事件的“字符串起始匹配”处理流装饰方法

    在前期的教程中，处理流装饰方法也称为绑定方法

    :param target: 匹配的目标字符串
    :param logic_mode: 匹配的逻辑模式
    :param checker: 检查器
    :param parser: 解析器
    :param priority: 优先级
    :param block: 是否阻断向低优先级传播
    :param temp: 是否临时使用（处理一次事件后停用）
    :param decos: 装饰器组
    :param legacy_session: 是否自动启用传统会话
    :return: 处理流装饰器
    """
    return FlowDecorator(
        checker_join(lambda e: isinstance(e, TextEvent), checker),  # type: ignore[arg-type]
        StartMatcher(target, logic_mode),
        parser,
        priority,
        block,
        temp,
        decos,
        DefaultRule() if legacy_session else None,
    )


def on_contain_match(
    target: str | Sequence[str],
    logic_mode: LogicMode = LogicMode.OR,
    checker: Checker | SyncOrAsyncCallable[[TextEvent], bool] | None = None,
    parser: Parser | None = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    legacy_session: bool = False,
) -> FlowDecorator:
    """绑定文本事件的“字符串包含匹配”处理流装饰方法

    在前期的教程中，处理流装饰方法也称为绑定方法

    :param target: 匹配的目标字符串
    :param logic_mode: 匹配的逻辑模式
    :param checker: 检查器
    :param parser: 解析器
    :param priority: 优先级
    :param block: 是否阻断向低优先级传播
    :param temp: 是否临时使用（处理一次事件后停用）
    :param decos: 装饰器组
    :param legacy_session: 是否自动启用传统会话
    :return: 处理流装饰器
    """
    return FlowDecorator(
        checker_join(lambda e: isinstance(e, TextEvent), checker),  # type: ignore[arg-type]
        ContainMatcher(target, logic_mode),
        parser,
        priority,
        block,
        temp,
        decos,
        DefaultRule() if legacy_session else None,
    )


def on_full_match(
    target: str | Sequence[str],
    logic_mode: LogicMode = LogicMode.OR,
    checker: Checker | SyncOrAsyncCallable[[TextEvent], bool] | None = None,
    parser: Parser | None = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    legacy_session: bool = False,
) -> FlowDecorator:
    """绑定文本事件的“字符串完整匹配”处理流装饰方法

    在前期的教程中，处理流装饰方法也称为绑定方法

    :param target: 匹配的目标字符串
    :param logic_mode: 匹配的逻辑模式
    :param checker: 检查器
    :param parser: 解析器
    :param priority: 优先级
    :param block: 是否阻断向低优先级传播
    :param temp: 是否临时使用（处理一次事件后停用）
    :param decos: 装饰器组
    :param legacy_session: 是否自动启用传统会话
    :return: 处理流装饰器
    """
    return FlowDecorator(
        checker_join(lambda e: isinstance(e, TextEvent), checker),  # type: ignore[arg-type]
        FullMatcher(target, logic_mode),
        parser,
        priority,
        block,
        temp,
        decos,
        DefaultRule() if legacy_session else None,
    )


def on_end_match(
    target: str | Sequence[str],
    logic_mode: LogicMode = LogicMode.OR,
    checker: Checker | SyncOrAsyncCallable[[TextEvent], bool] | None = None,
    parser: Parser | None = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    legacy_session: bool = False,
) -> FlowDecorator:
    """绑定文本事件的“字符串末尾匹配”处理流装饰方法

    在前期的教程中，处理流装饰方法也称为绑定方法

    :param target: 匹配的目标字符串
    :param logic_mode: 匹配的逻辑模式
    :param checker: 检查器
    :param parser: 解析器
    :param priority: 优先级
    :param block: 是否阻断向低优先级传播
    :param temp: 是否临时使用（处理一次事件后停用）
    :param decos: 装饰器组
    :param legacy_session: 是否自动启用传统会话
    :return: 处理流装饰器
    """
    return FlowDecorator(
        checker_join(lambda e: isinstance(e, TextEvent), checker),  # type: ignore[arg-type]
        EndMatcher(target, logic_mode),
        parser,
        priority,
        block,
        temp,
        decos,
        DefaultRule() if legacy_session else None,
    )


def on_regex_match(
    target: str,
    regex_flags: Any = 0,
    checker: Checker | SyncOrAsyncCallable[[TextEvent], bool] | None = None,
    parser: Parser | None = None,
    priority: int = 0,
    block: bool = False,
    temp: bool = False,
    decos: Sequence[Callable[[Callable], Callable]] | None = None,
    legacy_session: bool = False,
) -> FlowDecorator:
    """绑定文本事件的“正则匹配”处理流装饰方法

    在前期的教程中，处理流装饰方法也称为绑定方法

    :param target: 匹配的目标字符串
    :param regex_flags: 正则匹配的 flags
    :param checker: 检查器
    :param parser: 解析器
    :param priority: 优先级
    :param block: 是否阻断向低优先级传播
    :param temp: 是否临时使用（处理一次事件后停用）
    :param decos: 装饰器组
    :param legacy_session: 是否自动启用传统会话
    :return: 处理流装饰器
    """
    return FlowDecorator(
        checker_join(lambda e: isinstance(e, TextEvent), checker),  # type: ignore[arg-type]
        RegexMatcher(target, regex_flags),
        parser,
        priority,
        block,
        temp,
        decos,
        DefaultRule() if legacy_session else None,
    )
