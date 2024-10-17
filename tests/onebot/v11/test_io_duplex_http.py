import json
from asyncio import Queue, create_task

import aiohttp
import aiohttp.web

from melobot.ctx import LoggerCtx
from melobot.log.base import Logger
from melobot.protocols.onebot.v11.adapter import action
from melobot.protocols.onebot.v11.io.duplex_http import HttpIO
from melobot.protocols.onebot.v11.io.packet import OutPacket
from melobot.utils import singleton, to_async
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


async def put_input(s: str):
    async with aiohttp._ClientSession() as session:
        async with session.post("http://localhost:9090", json=json.loads(s)) as resp:
            return


_OUT_BUF = Queue()


@singleton
class MockClientSession:
    async def post(self, url, *args, **kwargs):
        await _OUT_BUF.put(
            json.dumps({"action": url.split("/")[-1], "params": kwargs["json"]})
        )
        resp = aiohttp.web.Response(status=200)
        resp.json = to_async(lambda: _TEST_ECHO_DICT | {"echo": _TEST_ACTION.id})
        return resp

    async def close(self):
        return


async def test_forward_ws(monkeypatch) -> None:
    with LoggerCtx().in_ctx(Logger()):
        aiohttp._ClientSession = aiohttp.ClientSession
        monkeypatch.setattr(aiohttp, "ClientSession", lambda: MockClientSession())
        io = HttpIO("localhost", 8080, "localhost", 9090)
        create_task(put_input(json.dumps(_TEST_EVENT_DICT)))

        async with io:
            await io.input()

            await put_input(json.dumps(_TEST_EVENT_DICT))
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
            pak = await t
            assert pak.data["data"]["hello"] == _TEST_ECHO_DICT["data"]["hello"]
            assert pak.ok == (_TEST_ECHO_DICT["status"] == "ok")
            assert pak.status == _TEST_ECHO_DICT["retcode"]
