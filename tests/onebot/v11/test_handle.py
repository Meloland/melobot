import asyncio
from asyncio import Queue, create_task

from melobot.bot import Bot
from melobot.log import GenericLogger
from melobot.plugin import Plugin
from melobot.protocols.onebot.v11 import handle
from melobot.protocols.onebot.v11.adapter.base import Adapter
from melobot.protocols.onebot.v11.adapter.event import MessageEvent
from melobot.protocols.onebot.v11.io.base import BaseIO
from melobot.protocols.onebot.v11.io.packet import EchoPacket, InPacket, OutPacket
from melobot.protocols.onebot.v11.utils import (
    CmdParser,
    GroupMsgChecker,
    LevelRole,
    ParseArgs,
)
from tests.base import *

_GRUOP_EVENT_DICT = {
    "time": 1725292489,
    "self_id": 123456,
    "post_type": "message",
    "message_type": "group",
    "sub_type": "normal",
    "sender": {
        "age": 0,
        "nickname": "这是一个群昵称",
        "sex": "unknown",
        "user_id": 3,
        "area": "",
        "card": "",
        "level": "",
        "role": "member",
        "title": "",
    },
    "message_id": -1234567890,
    "font": 0,
    "message": "\n\r\t .echo/123/456    \r\n",
    "user_id": 3,
    "anonymous": None,
    "group_id": 6,
    "raw_message": "45691237\n\r\t .echo/123/456    \r\n",
}


h = handle.on_start_match(
    ["123", "456"],
    checker=GroupMsgChecker(
        role=LevelRole.WHITE,
        owner=1,
        super_users=[2, 3],
        white_users=[4],
        black_users=[5],
        white_groups=[6, 7],
    ),
    parser=CmdParser(".", "/", "echo"),
)


@h
async def test_this(
    bot: Bot,
    event: MessageEvent,
    logger: GenericLogger,
    args: ParseArgs = handle.GetParseArgs(),
) -> None:
    logger.info(args)
    await bot.close()
    _SUCCESS_SIGNAL.set()


class TempPlugin(Plugin):
    version = "1.0.0"
    flows = [test_this]


class TempIO(BaseIO):
    def __init__(self) -> None:
        super().__init__(1)
        self.queue = Queue()
        self.queue.put_nowait(InPacket(data=_GRUOP_EVENT_DICT))

    async def open(self) -> None:
        pass

    def opened(self) -> bool:
        return True

    async def close(self) -> None:
        pass

    async def input(self) -> InPacket:
        return await self.queue.get()

    async def output(self, packet: OutPacket) -> EchoPacket:
        if packet.echo_id is None:
            return EchoPacket(noecho=True)


_SUCCESS_SIGNAL = asyncio.Event()


async def test_adapter_base():
    mbot = Bot("test_handle")
    mbot.add_io(TempIO())
    mbot.add_adapter(Adapter())
    mbot.load_plugin(TempPlugin())
    create_task(mbot.core_run())
    await mbot._rip_signal.wait()
    await _SUCCESS_SIGNAL.wait()
