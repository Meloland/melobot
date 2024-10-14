import asyncio
from asyncio import Queue, create_task

from melobot.adapter.generic import send_text
from melobot.bot import Bot
from melobot.handle import Flow, node
from melobot.log import GenericLogger
from melobot.plugin import Plugin
from melobot.protocols.onebot.v11.adapter.base import Adapter
from melobot.protocols.onebot.v11.adapter.event import MessageEvent
from melobot.protocols.onebot.v11.io.base import BaseIO
from melobot.protocols.onebot.v11.io.packet import EchoPacket, InPacket, OutPacket
from tests.base import *

_TEST_EVENT_DICT = {
    "time": 1725292489,
    "self_id": 123456,
    "post_type": "message",
    "message_type": "group",
    "sub_type": "normal",
    "sender": {
        "age": 0,
        "nickname": "这是一个群昵称",
        "sex": "unknown",
        "user_id": 1574260633,
        "area": "",
        "card": "",
        "level": "",
        "role": "member",
        "title": "",
    },
    "message_id": -1234567890,
    "font": 0,
    "message": "",
    "user_id": 1574260633,
    "anonymous": None,
    "group_id": 535705163,
    "raw_message": "",
}

_SUCCESS_SIGNAL = asyncio.Event()


class TempIO(BaseIO):
    def __init__(self) -> None:
        super().__init__(1)
        self.queue = Queue()
        self.queue.put_nowait(InPacket(data=_TEST_EVENT_DICT))

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
        return EchoPacket(
            data={"data": {"message_id": 123456}, "status": "ok", "retcode": 0},
            action_type="send_msg",
        )


@node
async def process(adapter: Adapter, event: MessageEvent, logger: GenericLogger) -> None:
    assert isinstance(event, MessageEvent)

    pending = await adapter.with_echo(send_text)("generic send test")
    assert (await pending[0]).data["message_id"] == 123456

    pending = await adapter.send_media("test.bmp", url="https://example.com/test.bmp")
    assert pending[0].action.params["message"][0]["type"] == "share"
    pending = await adapter.send_media("test.bmp", raw=b"123")
    assert pending[0].action.params["message"][0]["type"] == "text"

    pending = await adapter.send_image("test.jpg", url="https://example.com/test.jpg")
    assert pending[0].action.params["message"][0]["type"] == "image"

    pending = await adapter.send_file("test.txt", path="/home/abc/test.txt")
    assert pending[0].action.params["message"][0]["type"] == "text"

    pending = await adapter.send_refer(event)
    assert pending[0].action.params["message"][0]["type"] == "reply"

    pending = await adapter.send_resource("123456", "https://example.com/test.jpg")
    assert pending[0].action.params["message"][0]["type"] == "share"

    logger.info("adapter main event process ok")
    _SUCCESS_SIGNAL.set()


class TempPlugin(Plugin):
    version = "1.0.0"
    flows = [Flow("test_flow", [process])]


async def after_bot_started(bot: Bot):
    adapter = next(iter(bot.adapters.values()))
    pending = await adapter.with_echo(adapter.send_custom)("Hello World!", user_id=12345)
    data = (await pending[0]).data
    mid = data["message_id"]
    assert mid == 123456
    await bot.close()


async def test_adapter_base():
    mbot = Bot("test_adapter_base")
    mbot.add_io(TempIO())
    mbot.add_adapter(Adapter())
    mbot.load_plugin(TempPlugin())
    mbot.on_started(after_bot_started)
    create_task(mbot.core_run())
    await mbot._rip_signal.wait()
    await _SUCCESS_SIGNAL.wait()
