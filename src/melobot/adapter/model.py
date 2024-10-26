from __future__ import annotations

import asyncio
from asyncio import create_task
from contextlib import contextmanager
from dataclasses import dataclass, field
from time import time_ns
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Coroutine,
    Generator,
    Generic,
    Hashable,
    Literal,
    Sequence,
    cast,
)

from typing_extensions import LiteralString, Self, TypeVar

from ..ctx import ActionManualSignalCtx, Context, LoggerCtx
from ..exceptions import AdapterError
from ..log.base import LogLevel
from ..typ import T
from ..utils import AttrsReprable, get_id
from .content import Content

if TYPE_CHECKING:
    from .base import AbstractEchoFactory, AbstractOutputFactory, AbstractOutSource


class Event(AttrsReprable):
    """事件基类

    :ivar float time: 时间戳
    :ivar str id: id 标识
    :ivar typing.LiteralString | None protocol: 遵循的协议，为空则协议无关
    :ivar typing.Sequence[Content] contents: 附加的通用内容序列
    :ivar typing.Hashable | None scope: 所在的域，可空
    """

    def __init__(
        self,
        time: float = -1,
        id: str = "",
        protocol: LiteralString | None = None,
        scope: Hashable | None = None,
        contents: Sequence[Content] | None = None,
    ) -> None:
        self.time = time_ns() / 1e9 if time == -1 else time
        self.id = get_id() if id == "" else id
        self.protocol = protocol
        self.contents = contents if contents else ()
        self.scope = scope

        self.spread: bool = True


EventT = TypeVar("EventT", bound=Event)


class Action(AttrsReprable):
    """行为基类

    :ivar float time: 时间戳
    :ivar str id: id 标识
    :ivar typing.LiteralString | None protocol: 遵循的协议，为空则协议无关
    :ivar typing.Sequence[Content] contents: 附加的通用内容序列
    :ivar typing.Hashable | None scope: 所在的域，可空
    :ivar Event | None trigger: 触发该行为的事件，为空表明不由事件触发
    """

    def __init__(
        self,
        time: float = -1,
        id: str = "",
        protocol: LiteralString | None = None,
        scope: Hashable | None = None,
        contents: Sequence[Content] | None = None,
        trigger: Event | None = None,
    ) -> None:
        self.time = time_ns() / 1e9 if time == -1 else time
        self.id = get_id() if id == "" else id
        self.protocol = protocol
        self.contents = contents if contents else ()
        self.scope = scope
        self.trigger = trigger


class Echo(AttrsReprable):
    """回应基类

    :ivar float time: 时间戳
    :ivar str id: id 标识
    :ivar typing.LiteralString | None protocol: 遵循的协议，为空则协议无关
    :ivar typing.Hashable | None scope: 所在的域，可空
    :ivar bool ok: 回应是否成功
    :ivar int status: 回应状态码
    :ivar str prompt: 回应提示语
    :ivar Any data: 回应数据
    """

    def __init__(
        self,
        time: float = -1,
        id: str = "",
        protocol: LiteralString | None = None,
        scope: Hashable | None = None,
        ok: bool = True,
        status: int = 0,
        prompt: str = "",
        data: Any = None,
    ) -> None:
        self.time = time_ns() / 1e9 if time == -1 else time
        self.id = get_id() if id == "" else id
        self.protocol = protocol
        self.scope = scope
        self.ok = ok
        self.status = status
        self.prompt = prompt
        self.data = data


ActionT = TypeVar("ActionT", bound=Action)
EchoT = TypeVar("EchoT", bound=Echo)


ActionRetT = TypeVar("ActionRetT", bound=Echo | None)


class ActionHandle(Generic[ActionRetT]):
    """行为操作句柄

    :ivar Action action: 操作包含的行为对象
    :ivar typing.Literal["PENDING", "EXECUTING", "FINISHED"] status: 操作的状态。分别对应：未执行、执行中、执行完成
    """

    def __init__(
        self,
        action: Action,
        out_src: "AbstractOutSource",
        output_factory: "AbstractOutputFactory",
        echo_factory: "AbstractEchoFactory",
    ) -> None:
        self.action = action
        self.status: Literal["PENDING", "EXECUTING", "FINISHED"] = "PENDING"

        self._echo: ActionRetT
        self._out_src = out_src
        self._output_factory = output_factory
        self._echo_factory = echo_factory
        self._done = asyncio.Event()

        if not ActionManualSignalCtx().try_get():
            self.execute()

    async def _wait(self) -> ActionRetT:
        await self._done.wait()
        return self._echo

    def __await__(self) -> Generator[Any, Any, ActionRetT]:
        """本对象实现 __await__ 接口，因此可等待。返回本操作对应的回应数据"""
        return self._wait().__await__()

    async def _execute(self) -> None:
        try:
            output_packet = await self._output_factory.create(self.action)
            echo_packet = await self._out_src.output(output_packet)
            self._echo = cast(ActionRetT, await self._echo_factory.create(echo_packet))
            self.status = "FINISHED"
            self._done.set()
        except Exception:
            logger = LoggerCtx().get()
            logger.exception(f"{self.action} 执行时出现异常")
            logger.generic_obj("异常点局部变量", locals(), level=LogLevel.ERROR)

    def execute(self) -> Self:
        if self.status != "PENDING":
            raise AdapterError("行为操作正在执行或执行完毕，不应该再执行")

        self.status = "EXECUTING"
        create_task(self._execute())
        return self


@dataclass
class _ChainStep:
    coros: Sequence[Coroutine]
    ret_when: Literal["FIRST_COMPLETED", "FIRST_EXCEPTION", "ALL_COMPLETED"]
    next: _ChainStep | None = None


@dataclass(kw_only=True)
class _ChainCtxStep(_ChainStep):
    ctx_var: Context
    ctx_val: Any
    coros: Sequence[Coroutine] = field(default_factory=tuple)
    ret_when: Literal["ALL_COMPLETED"] = "ALL_COMPLETED"


class ActionChain:
    """行为链"""

    def __init__(self) -> None:
        self._chain: list[_ChainStep] = []

    def _add_step(self, step: _ChainStep) -> None:
        if len(self._chain):
            self._chain[-1].next = step
        self._chain.append(step)

    def in_ctx(self, ctx: Context[T], val: T) -> Self:
        """指定链后续的步骤中在 `ctx` 类别的上下文中执行，上下文值为 `val`

        :param ctx: 上下文类别
        :param val: 上下文的值
        :return: 自身，因此支持链式调用
        """
        self._add_step(_ChainCtxStep(ctx_var=ctx, ctx_val=val))
        return self

    async def _exec_handle(self, handles: Awaitable[tuple[ActionHandle, ...]]) -> None:
        _handles = await handles
        for handle in _handles:
            handle.execute()
        await asyncio.wait(_handles)

    def add(
        self,
        *handles: Awaitable[tuple[ActionHandle, ...]],
        ret_when: Literal[
            "FIRST_COMPLETED", "FIRST_EXCEPTION", "ALL_COMPLETED"
        ] = "ALL_COMPLETED",
    ) -> Self:
        """在链的步骤中添加一组行为

        :param handles: 返回行为操作句柄的可等待对象
        :param ret_when: 指定这一组行为的等待模式
        :return: 自身，因此支持链式调用
        """
        coros = tuple(self._exec_handle(hs) for hs in handles)
        self._add_step(_ChainStep(coros, ret_when))
        return self

    def sleep(self, interval: float) -> Self:
        """
        在链的步骤中添加指定时长的等待

        :param interval: 等待时长
        :return: 自身，因此支持链式调用
        """
        coros = (asyncio.sleep(interval),)
        self._add_step(_ChainStep(coros, ret_when="ALL_COMPLETED"))
        return self

    async def _start(self, step: _ChainStep) -> None:
        if isinstance(step, _ChainCtxStep):
            with step.ctx_var.in_ctx(step.ctx_val):
                if step.next:
                    await self._start(step.next)
            return

        if len(step.coros):
            await asyncio.wait(map(create_task, step.coros), return_when=step.ret_when)
        if step.next:
            await self._start(step.next)

    async def run(self) -> None:
        """顺序执行链的所有步骤"""
        await self._start(self._chain[0])


@contextmanager
def open_chain() -> Generator[ActionChain, None, None]:
    """创建行为链的上下文管理器

    :yield: 行为链对象
    """
    with ActionManualSignalCtx().in_ctx(True):
        yield ActionChain()
