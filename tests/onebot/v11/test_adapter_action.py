from melobot.protocols.onebot.v11.adapter import action
from melobot.protocols.onebot.v11.adapter import segment as seg
from tests.base import *


async def test_base():
    a = action.Action("test", {"hi": True, "you": 123.45})
    a.set_echo(True)
    assert a.need_echo
    assert a.flatten().startswith(
        '{"action": "test", "params": {"hi": true, "you": 123.45}'
    )


async def test_msgs_to_dicts():
    out = [{"type": "text", "data": {"text": "123"}}]

    msgs = "123"
    assert action.msgs_to_dicts(msgs) == out
    msgs = seg.Segment("text", text="123")
    assert action.msgs_to_dicts(msgs) == out
    msgs = [seg.Segment("text", text="123")]
    assert action.msgs_to_dicts(msgs) == out
    msgs = {"type": "text", "data": {"text": "123"}}
    assert action.msgs_to_dicts(msgs) == out
    msgs = [{"type": "text", "data": {"text": "123"}}]
    assert action.msgs_to_dicts(msgs) == out
