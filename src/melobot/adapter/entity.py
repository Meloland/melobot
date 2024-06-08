import asyncio
import time

from typing_extensions import Self

from ..exceptions import BotRuntimeError
from ..typing import (
    Any,
    AsyncCallable,
    BetterABC,
    Generic,
    Literal,
    LiteralString,
    NamedTuple,
    Optional,
    Sequence,
    TypeVar,
    abstractattr,
    cast,
)
from ..utils import get_id
from .content import AbstractContent


class AbstractEntity(BetterABC):
    type: str | None = abstractattr()
    time: int = abstractattr()
    id: str = abstractattr()
    protocol: LiteralString | None = abstractattr()
    scope: Optional[NamedTuple] = abstractattr()


class BaseEvent(AbstractEntity):
    def __init__(
        self,
        type: str | None = None,
        time: int = time.time_ns(),
        id: str = get_id(),
        protocol: LiteralString | None = None,
        scope: Optional[NamedTuple] = None,
        contents: Sequence[AbstractContent] = (),
    ) -> None:
        self.type = type
        self.time = time
        self.id = id
        self.protocol = protocol
        self.contents = contents
        self.scope = scope


Event_T = TypeVar("Event_T", bound=BaseEvent)


class BaseAction(AbstractEntity):
    def __init__(
        self,
        type: str | None = None,
        time: int = time.time_ns(),
        id: str = get_id(),
        protocol: LiteralString | None = None,
        scope: Optional[NamedTuple] = None,
        contents: Sequence[AbstractContent] = (),
        trigger: Event_T | None = None,
    ) -> None:
        self.type = type
        self.time = time
        self.id = id
        self.protocol = protocol
        self.contents = contents
        self.scope = scope
        self.trigger = trigger


class BaseEcho(AbstractEntity):
    def __init__(
        self,
        type: str | None = None,
        time: int = time.time_ns(),
        id: str = get_id(),
        protocol: LiteralString | None = None,
        scope: Optional[NamedTuple] = None,
        ok: bool = True,
        status: int = 0,
        prompt: str = "",
        data: Any = None,
    ) -> None:
        self.type = type
        self.time = time
        self.id = id
        self.protocol = protocol
        self.scope = scope
        self.ok = ok
        self.status = status
        self.prompt = prompt
        self.data = data


Action_T = TypeVar("Action_T", bound=BaseAction)
Echo_T = TypeVar("Echo_T", bound=BaseEcho)


class ActionHandle(Generic[Action_T, Echo_T]):
    def __init__(
        self,
        action: Action_T,
        exec_meth: AsyncCallable[[Action_T], asyncio.Future[Echo_T] | None],
        wait: bool,
    ) -> None:
        #: 本操作包含的行为对象
        self.action: Action_T = action
        #: 本操作当前状态。分别对应：未执行、执行中、执行完成
        self.status: Literal["PENDING", "EXECUTING", "FINISHED"] = "PENDING"

        self._echo: Echo_T
        self._wait = wait
        self._exec_meth = exec_meth
        self._echo_done = asyncio.Event()

    @property
    async def echo(self) -> Echo_T:
        if not self._wait:
            raise BotRuntimeError("行为操作未指定等待，无法获取回应")

        await self._echo_done.wait()
        return self._echo

    def __await__(self):
        yield

    async def wait(self) -> None:
        if not self._wait:
            raise BotRuntimeError("行为操作未指定等待，无法等待")
        await self._echo_done.wait()

    async def _execute(self) -> None:
        ret = await self._exec_meth(self.action)
        if self._wait:
            ret = cast(asyncio.Future[Echo_T], ret)
            self._echo = await ret
            self._echo_done.set()

        self.status = "FINISHED"

    def execute(self) -> Self:
        if self.status != "PENDING":
            raise BotRuntimeError("行为操作正在执行或执行完毕，不应该再执行")

        self.status = "EXECUTING"
        asyncio.create_task(self._execute())
        return self
