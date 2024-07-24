import asyncio
from time import time_ns

from typing_extensions import Self

from ..abc import AttrsReprMixin
from ..exceptions import BotRuntimeError
from ..io.abc import EchoPacket_T, InPacket_T, OutPacket_T
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
    abstractmethod,
    cast,
)
from ..utils import get_id
from .content import AbstractContent


class Event(AttrsReprMixin):
    def __init__(
        self,
        type: str | None = None,
        time: int = -1,
        id: str = "",
        protocol: LiteralString | None = None,
        scope: Optional[NamedTuple] = None,
        contents: Sequence[AbstractContent] = (),
    ) -> None:
        self.type = type
        self.time = time_ns() if time == -1 else time
        self.id = get_id() if id == "" else id
        self.protocol = protocol
        self.contents = contents
        self.scope = scope


Event_T = TypeVar("Event_T", bound=Event)


class Action(AttrsReprMixin):
    def __init__(
        self,
        type: str | None = None,
        time: int = -1,
        id: str = "",
        protocol: LiteralString | None = None,
        scope: Optional[NamedTuple] = None,
        contents: Sequence[AbstractContent] = (),
        trigger: Event | None = None,
    ) -> None:
        self.type = type
        self.time = time_ns() if time == -1 else time
        self.id = get_id() if id == "" else id
        self.protocol = protocol
        self.contents = contents
        self.scope = scope
        self.trigger = trigger


class Echo(AttrsReprMixin):
    def __init__(
        self,
        type: str | None = None,
        time: int = -1,
        id: str = "",
        protocol: LiteralString | None = None,
        scope: Optional[NamedTuple] = None,
        ok: bool = True,
        status: int = 0,
        prompt: str = "",
        data: Any = None,
    ) -> None:
        self.type = type
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


class AbstractEventFactory(BetterABC, Generic[InPacket_T, Event_T]):
    @abstractmethod
    def create(self, packet: InPacket_T) -> Event_T:
        raise NotImplementedError


class AbstractOutputFactory(BetterABC, Generic[OutPacket_T, Action_T]):
    @abstractmethod
    def create(self, action: Action_T) -> OutPacket_T:
        raise NotImplementedError


class AbstractEchoFactory(BetterABC, Generic[EchoPacket_T, Echo_T]):
    @abstractmethod
    def create(self, packet: EchoPacket_T) -> Echo_T:
        raise NotImplementedError


class AbstractAdapter(
    BetterABC,
    Generic[Event_T, Action_T, Echo_T, InPacket_T, OutPacket_T, EchoPacket_T],
):
    protocol: LiteralString = abstractattr()
    event_factory: AbstractEventFactory[InPacket_T, Event_T] = abstractattr()
    action_factory: AbstractOutputFactory[OutPacket_T, Action_T] = abstractattr()
    echo_factory: AbstractEchoFactory[EchoPacket_T, Echo_T] = abstractattr()


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
