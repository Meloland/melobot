import asyncio
from asyncio import create_task
from time import time_ns

from ..exceptions import BotRuntimeError
from ..typ import (
    TYPE_CHECKING,
    Any,
    AttrsReprMixin,
    Generator,
    Generic,
    Literal,
    LiteralString,
    NamedTuple,
    Optional,
    Self,
    Sequence,
    TypeVar,
    cast,
)
from ..utils import get_id
from .content import AbstractContent

if TYPE_CHECKING:
    from .base import AbstractEchoFactory, AbstractOutputFactory, AbstractOutSource


class Event(AttrsReprMixin):
    def __init__(
        self,
        time: int = -1,
        id: str = "",
        protocol: LiteralString | None = None,
        scope: Optional[NamedTuple] = None,
        contents: Sequence[AbstractContent] = (),
    ) -> None:
        self.time = time_ns() if time == -1 else time
        self.id = get_id() if id == "" else id
        self.protocol = protocol
        self.contents = contents
        self.scope = scope

        self._spread: bool = True


Event_T = TypeVar("Event_T", bound=Event)


class Action(AttrsReprMixin):
    def __init__(
        self,
        time: int = -1,
        id: str = "",
        protocol: LiteralString | None = None,
        scope: Optional[NamedTuple] = None,
        contents: Sequence[AbstractContent] = (),
        trigger: Event | None = None,
    ) -> None:
        self.time = time_ns() if time == -1 else time
        self.id = get_id() if id == "" else id
        self.protocol = protocol
        self.contents = contents
        self.scope = scope
        self.trigger = trigger


class Echo(AttrsReprMixin):
    def __init__(
        self,
        time: int = -1,
        id: str = "",
        protocol: LiteralString | None = None,
        scope: Optional[NamedTuple] = None,
        ok: bool = True,
        status: int = 0,
        prompt: str = "",
        data: Any = None,
    ) -> None:
        self.time = time_ns() if time == -1 else time
        self.id = get_id() if id == "" else id
        self.protocol = protocol
        self.scope = scope
        self.ok = ok
        self.status = status
        self.prompt = prompt
        self.data = data


Action_T = TypeVar("Action_T", bound=Action)
Echo_T = TypeVar("Echo_T", bound=Echo)


HandleRet_T = TypeVar("HandleRet_T", bound=Echo | None)


class ActionHandle(Generic[HandleRet_T]):
    def __init__(
        self,
        action: Action,
        out_src: "AbstractOutSource",
        output_factory: "AbstractOutputFactory",
        echo_factory: "AbstractEchoFactory",
    ) -> None:
        #: 本操作包含的行为对象
        self.action = action
        #: 本操作当前状态。分别对应：未执行、执行中、执行完成
        self.status: Literal["PENDING", "EXECUTING", "FINISHED"] = "PENDING"

        self._echo: HandleRet_T
        self._out_src = out_src
        self._output_factory = output_factory
        self._echo_factory = echo_factory
        self._echo_done = asyncio.Event()

        self.execute()

    async def _wait(self) -> HandleRet_T:
        await self._echo_done.wait()
        return self._echo

    def __await__(self) -> Generator[Any, Any, HandleRet_T]:
        return self._wait().__await__()

    async def _execute(self) -> None:
        output_packet = await self._output_factory.create(self.action)
        echo_packet = await self._out_src.output(output_packet)
        self._echo = cast(HandleRet_T, await self._echo_factory.create(echo_packet))
        self.status = "FINISHED"
        self._echo_done.set()

    def execute(self) -> Self:
        if self.status != "PENDING":
            raise BotRuntimeError("行为操作正在执行或执行完毕，不应该再执行")

        self.status = "EXECUTING"
        create_task(self._execute())
        return self
