import asyncio
from asyncio import Queue

from melobot.bot import Bot
from melobot.handle import Flow, node
from melobot.log import logger
from melobot.plugin import PluginPlanner
from melobot.protocols.onebot.v11.adapter.base import Adapter
from melobot.protocols.onebot.v11.adapter.event import MessageEvent
from melobot.protocols.onebot.v11.io.base import BaseIOSource
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


class TempIO(BaseIOSource):
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
async def process(adapter: Adapter, event: MessageEvent) -> None:
    assert isinstance(event, MessageEvent)

    pending = await adapter.send("generic send test")
    assert (await pending[0]).data["message_id"] == 123456

    pending = await adapter.__send_media__("test.bmp", url="https://example.com/test.bmp")
    assert pending[0].action.params["message"][0]["type"] == "share"
    pending = await adapter.__send_media__("test.bmp", raw=b"123")
    assert pending[0].action.params["message"][0]["type"] == "text"

    pending = await adapter.__send_image__("test.jpg", url="https://example.com/test.jpg")
    assert pending[0].action.params["message"][0]["type"] == "image"

    pending = await adapter.__send_file__("test.txt", path="/home/abc/test.txt")
    assert pending[0].action.params["message"][0]["type"] == "text"

    pending = await adapter.__send_refer__(event)
    assert pending[0].action.params["message"][0]["type"] == "reply"

    pending = await adapter.__send_resource__("123456", "https://example.com/test.jpg")
    assert pending[0].action.params["message"][0]["type"] == "share"

    logger.info("adapter main event process ok")
    _SUCCESS_SIGNAL.set()


async def after_bot_started(bot: Bot, adapter: Adapter):
    pending = await adapter.send_custom("Hello World!", user_id=12345)
    data = (await pending[0]).data
    mid = data["message_id"]
    assert mid == 123456
    await _SUCCESS_SIGNAL.wait()
    await bot.close()


async def test_adapter_base():
    mbot = Bot("test_adapter_base")
    mbot.add_io(TempIO())
    mbot.add_adapter(Adapter())

    flow = Flow("test_adapter_base", [process])
    mbot.load_plugin(PluginPlanner("1.0.0", flows=[flow]))
    mbot.on_started(after_bot_started)
    await mbot.run_async()
    await _SUCCESS_SIGNAL.wait()
