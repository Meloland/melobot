import json
from asyncio import Queue, create_task

import websockets

from melobot.ctx import LoggerCtx
from melobot.log.base import Logger
from melobot.protocols.onebot.v11.adapter import action
from melobot.protocols.onebot.v11.io.packet import OutPacket
from melobot.protocols.onebot.v11.io.reverse import ReverseWebSocketIO
from melobot.utils import singleton
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
_TEST_ACTION = action.SendMsgAction("hello world!", 123)
_TEST_ECHO_DICT = {
    "time": 1725292489,
    "status": "ok",
    "retcode": 0,
    "data": {"hello": "world!"},
}


_IN_BUF = Queue()
_OUT_BUF = Queue()


@singleton
class MockWebsocket:
    close_timeout = 0

    def __init__(self, loop_func) -> None:
        self.input_loop = loop_func

    @staticmethod
    async def get(loop_func, *args, **kwargs):
        obj = MockWebsocket(loop_func)
        create_task(obj.input_loop(obj))
        return obj

    async def send(self, data: str) -> None:
        await _OUT_BUF.put(data)

    async def recv(self) -> str:
        return await _IN_BUF.get()

    async def close(self):
        return

    async def wait_closed(self) -> None:
        return


async def test_forward_ws(monkeypatch) -> None:
    with LoggerCtx().in_ctx(Logger()):
        monkeypatch.setattr(websockets, "serve", MockWebsocket.get)
        io = ReverseWebSocketIO("localhost", 8080)
        async with io:

            await _IN_BUF.put(json.dumps(_TEST_EVENT_DICT))
            pak = await io.input()
            assert pak.data == _TEST_EVENT_DICT

            pak = await io.output(
                OutPacket(
                    data=_TEST_ACTION.extract(),
                    action_type=_TEST_ACTION.extract()["action"],
                    action_params=_TEST_ACTION.extract()["params"],
                )
            )
            await _OUT_BUF.get() == _TEST_ACTION.flatten()
            assert pak.noecho

            _TEST_ACTION.set_echo(True)
            t = create_task(
                io.output(
                    OutPacket(
                        data=_TEST_ACTION.extract(),
                        action_type=_TEST_ACTION.extract()["action"],
                        action_params=_TEST_ACTION.extract()["params"],
                        echo_id=_TEST_ACTION.extract()["echo"],
                    )
                )
            )
            await _OUT_BUF.get() == _TEST_ACTION.flatten()
            await _IN_BUF.put(
                json.dumps(_TEST_ECHO_DICT | {"echo": _TEST_ACTION.extract()["echo"]})
            )
            pak = await t
            assert pak.data["data"]["hello"] == _TEST_ECHO_DICT["data"]["hello"]
            assert pak.ok == (_TEST_ECHO_DICT["status"] == "ok")
            assert pak.status == _TEST_ECHO_DICT["retcode"]
