import asyncio
import sys

from typing_extensions import Any, cast

from melobot import get_bot
from melobot.adapter import (
    AbstractEchoFactory,
    AbstractEventFactory,
    AbstractOutputFactory,
    ActionHandleGroup,
)
from melobot.adapter import Adapter as RootAdapter
from melobot.adapter import content as mc
from melobot.exceptions import AdapterError
from melobot.typ import SyncOrAsyncCallable

from ..const import PROTOCOL_IDENTIFIER
from ..io.model import EchoPacket, InPacket, NormalOutputData, OutPacket, OutputType, RawOutputData
from ..io.src import ConsoleIO
from . import action as ac
from . import echo as ec
from . import event as ev


class EventFactory(AbstractEventFactory[InPacket, ev.Event]):
    async def create(self, packet: InPacket) -> ev.Event:
        event = ev.Event.resolve(packet.data)
        asyncio.create_task(get_bot().wait_finish(event)).add_done_callback(
            lambda *_, **__: packet.finished.set_result(None)
        )
        return event


class OutputFactory(AbstractOutputFactory[OutPacket, ac.Action]):
    async def create(self, action: ac.Action) -> OutPacket:
        match action.type:
            case OutputType.STDOUT_OR_STDERR:
                action = cast(ac.NormalOutputAction, action)
                return OutPacket(
                    data=NormalOutputData(
                        content=action.msg,
                        stream=sys.stdout if action.is_stdout else sys.stderr,
                        next_prompt_args=action.next_prompt_args,
                    )
                )
            case OutputType.RAW_OUTPUT:
                action = cast(ac.RawOutputAction, action)
                return OutPacket(
                    data=RawOutputData(
                        executor=action.executor, next_prompt_args=action.next_prompt_args
                    )
                )
            case _:
                raise ValueError(f"不支持的行为操作：{action}")


class EchoFactory(AbstractEchoFactory[EchoPacket, ec.Echo]):
    async def create(self, packet: EchoPacket) -> ec.Echo | None:
        if packet.noecho:
            return None
        raise ValueError("暂不支持 Echo 功能，但输入输出管理器提供了异常的标识")


class Adapter(
    RootAdapter[EventFactory, OutputFactory, EchoFactory, ac.Action, ConsoleIO, ConsoleIO]
):
    def __init__(self) -> None:
        super().__init__(PROTOCOL_IDENTIFIER, EventFactory(), OutputFactory(), EchoFactory())

    async def send(
        self,
        msg: str,
        stderr: bool = False,
        next_prompt_args: dict[str, Any] | None = None,
    ) -> ActionHandleGroup[ec.Echo]:
        return await self.call_output(
            ac.NormalOutputAction(msg, "stderr" if stderr else "stdout", next_prompt_args)
        )

    async def raw_output(
        self, executor: SyncOrAsyncCallable[[], Any], next_prompt_args: dict[str, Any] | None = None
    ) -> ActionHandleGroup[ec.Echo]:
        return await self.call_output(ac.RawOutputAction(executor, next_prompt_args))

    async def __send_text__(self, *texts: str | mc.TextContent) -> ActionHandleGroup[ec.Echo]:
        s = "".join(t if isinstance(t, str) else t.text for t in texts)
        if s == "":
            raise AdapterError("发送文本消息时，内容不能为空")
        return await self.send(s)
