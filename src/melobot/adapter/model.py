from __future__ import annotations

import asyncio
from asyncio import create_task
from contextlib import contextmanager
from time import time_ns

from typing_extensions import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Generator,
    Generic,
    Hashable,
    Iterator,
    Literal,
    LiteralString,
    Self,
    Sequence,
    TypeVar,
    cast,
)

from ..ctx import ActionAutoExecCtx, EventOrigin
from ..exceptions import ActionHandleError
from ..io.base import AbstractOutSource
from ..mixin import AttrReprMixin, FlagMixin
from ..typ.cls import BetterABC, abstractattr
from ..utils.common import get_id
from .content import Content

if TYPE_CHECKING:
    from .base import AbstractEchoFactory, AbstractOutputFactory


class Event(AttrReprMixin, FlagMixin):
    """事件基类

    :ivar typing.LiteralString protocol: 遵循的协议，为空则协议无关
    :ivar float time: 时间戳
    :ivar str id: id 标识
    :ivar typing.Hashable | None scope: 所在的域，可空
    :ivar typing.Sequence[Content] contents: 附加的通用内容序列
    """

    def __init__(
        self,
        protocol: LiteralString,
        time: float = -1,
        id: str = "",
        scope: Hashable | None = None,
        contents: Sequence[Content] | None = None,
    ) -> None:
        super().__init__()

        self.time = time_ns() / 1e9 if time == -1 else time
        self.id = get_id() if id == "" else id
        self.protocol = protocol
        self.contents = contents if contents else ()
        self.scope = scope

        self.spread: bool = True

    def get_origin_info(self) -> EventOrigin:
        return EventOrigin.get_origin(self)


EventT = TypeVar("EventT", bound=Event)


class TextEvent(Event, BetterABC):
    """文本事件类

    :ivar str text: 文本内容
    :ivar list[str] textlines: 文本分行内容
    """

    text: str = abstractattr()
    """:meta hide-value:"""

    textlines: list[str] = abstractattr()
    """:meta hide-value:"""


class Action(AttrReprMixin, FlagMixin):
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
        super().__init__()
        self.time = time_ns() / 1e9 if time == -1 else time
        self.id = get_id() if id == "" else id
        self.protocol = protocol
        self.contents = contents if contents else ()
        self.scope = scope
        self.trigger = trigger


class Echo(AttrReprMixin, FlagMixin):
    """回应基类

    :ivar float time: 时间戳
    :ivar str id: id 标识
    :ivar typing.LiteralString | None protocol: 遵循的协议，为空则协议无关
    :ivar typing.Hashable | None scope: 所在的域，可空
    :ivar int status: 回应状态码
    :ivar str prompt: 回应提示语
    """

    def __init__(
        self,
        time: float = -1,
        id: str = "",
        protocol: LiteralString | None = None,
        scope: Hashable | None = None,
        status: int = 0,
        prompt: str = "",
    ) -> None:
        super().__init__()
        self.time = time_ns() / 1e9 if time == -1 else time
        self.id = get_id() if id == "" else id
        self.protocol = protocol
        self.scope = scope
        self.status = status
        self.prompt = prompt


ActionT = TypeVar("ActionT", bound=Action)
EchoT = TypeVar("EchoT", bound=Echo)


class ActionHandleGroup(Generic[EchoT]):
    """行为操作句柄组"""

    def __init__(self, *handles: ActionHandle[EchoT]) -> None:
        self._handles = handles

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(all: {len(self._handles)}, "
            f"done: {len(tuple(h for h in self._handles if h.status == 'DONE'))})"
        )

    def __getitem__(self, idx: int) -> ActionHandle[EchoT]:
        return self._handles[idx]

    def __len__(self) -> int:
        return len(self._handles)

    def __bool__(self) -> bool:
        return True

    def __iter__(self) -> Iterator[ActionHandle[EchoT]]:
        return iter(self._handles)

    async def __aiter__(self) -> AsyncIterator[tuple[EchoT | None, ActionHandle[EchoT]]]:
        waits = (h._await_ret_self() for h in self._handles)
        for fut in asyncio.as_completed(waits):
            yield await fut

    async def unwrap_iter(self) -> AsyncIterator[EchoT]:
        waits = (h._await_ret_self() for h in self._handles)
        for fut in asyncio.as_completed(waits):
            echo, h = await fut
            if echo is None:
                raise ActionHandleError(
                    "迭代获取行为操作的回应失败，迭代时出现为 None 的回应", handle=h
                )
            yield echo

    def __await__(self) -> Generator[Any, Any, list[EchoT | None]]:
        return self._await_all().__await__()

    async def unwrap(self, idx: int) -> EchoT:
        handle = self._handles[idx]
        echo = await handle
        if echo is None:
            raise ActionHandleError(
                f"对行为操作 {self.unwrap.__name__} 失败，因为操作的回应为 None", handle=handle
            )
        return echo

    async def unwrap_all(self) -> list[EchoT]:
        echoes = await self._await_all()
        for idx, e in enumerate(echoes):
            if e is None:
                raise ActionHandleError(
                    f"对行为操作组 {self.unwrap_all.__name__} 失败，因为操作组的回应中有 None",
                    handle=self._handles[idx],
                )
        return cast(list[EchoT], echoes)

    async def _await_all(self) -> list[EchoT | None]:
        echoes = await asyncio.gather(*self._handles)
        return echoes

    def execute(self) -> None:
        for h in self._handles:
            h.execute()


class ActionHandle(Generic[EchoT]):
    """行为操作句柄

    :ivar Action action: 操作包含的行为对象
    :ivar typing.Literal["PENDING", "EXECUTING", "DONE"] status: 操作的状态。分别对应：未执行、执行中、执行完成
    :ivar AbstractOutSource out_src: 执行操作的输出源对象
    """

    def __init__(
        self,
        action: Action,
        out_src: AbstractOutSource,
        output_factory: "AbstractOutputFactory",
        echo_factory: "AbstractEchoFactory",
    ) -> None:
        self.action = action
        self.status: Literal["PENDING", "EXECUTING", "DONE"] = "PENDING"
        self.out_src = out_src

        self._echo_fut: asyncio.Future[EchoT | None] = asyncio.Future()
        self._output_factory = output_factory
        self._echo_factory = echo_factory

        if ActionAutoExecCtx().try_get(True):
            self.execute()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(status={self.status}, fut={self._echo_fut})"

    def __await__(self) -> Generator[Any, Any, EchoT | None]:
        # 并发多次 await 是安全的，未触发执行任务时 await 也是安全的
        return self._echo_fut.__await__()

    async def _await_ret_self(self) -> tuple[EchoT | None, Self]:
        echo = await self._echo_fut
        return echo, self

    def execute(self) -> Self:
        if self.status != "PENDING":
            raise RuntimeError("行为操作正在执行或执行完毕，不应该再执行")
        self.status = "EXECUTING"
        create_task(self._execute())
        return self

    async def _execute(self) -> None:
        try:
            output_packet = await self._output_factory.create(self.action)
            echo_packet = await self.out_src.output(output_packet)
            echo = await self._echo_factory.create(echo_packet)
            self._echo_fut.set_result(echo)
        except Exception as e:
            self._echo_fut.set_exception(e)
            if isinstance(e, asyncio.CancelledError):
                raise
        finally:
            self.status = "DONE"


@contextmanager
def lazy_action() -> Generator[None, None, None]:
    """手动执行行为操作的上下文管理器

    展开一个行为操作不自动执行的上下文，适用于需要手动干预行为操作执行时机的场景
    """
    with ActionAutoExecCtx().unfold(False):
        yield
