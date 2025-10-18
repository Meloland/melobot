import asyncio
from asyncio import Queue

from melobot.bot import Bot
from melobot.handle import on_start_match
from melobot.log import logger
from melobot.plugin import PluginPlanner
from melobot.protocols.onebot.v11.adapter.base import Adapter
from melobot.protocols.onebot.v11.io.base import BaseIOSource
from melobot.protocols.onebot.v11.io.packet import EchoPacket, InPacket, OutPacket
from melobot.protocols.onebot.v11.utils import GroupMsgChecker, LevelRole
from melobot.utils.parse import CmdArgs, CmdParser
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
    "raw_message": "\n\r\t .echo/123/456    \r\n",
}


h = on_start_match(
    ["\n\r\t .echo"],
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
async def _flow(bot: Bot, args: CmdArgs) -> None:
    logger.info(args)
    await bot.close()
    _SUCCESS_SIGNAL.set()


class TempIO(BaseIOSource):
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


async def test_handle():
    mbot = Bot("test_handle")
    mbot.add_io(TempIO())
    mbot.add_adapter(Adapter())
    mbot.load_plugin(PluginPlanner("1.0.0", flows=[_flow]))
    await mbot.run_async()
    await _SUCCESS_SIGNAL.wait()
