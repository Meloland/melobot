from asyncio import Queue

from melobot.protocols.onebot.v11.adapter import event
from melobot.protocols.onebot.v11.adapter.segment import AtSegment
from melobot.protocols.onebot.v11.utils import (
    AtMsgChecker,
    GroupRole,
    LevelRole,
    MsgCheckerFactory,
)
from tests.base import *

_CB_BUF = Queue()
_PRIVATE_EVENT_DICT = {
    "time": 1725292489,
    "self_id": 123456,
    "post_type": "message",
    "message_type": "private",
    "sub_type": "friend",
    "sender": {
        "age": 0,
        "sex": "unknown",
        "nickname": "这是一个昵称",
        "user_id": 1574260633,
    },
    "message_id": -1234567890,
    "font": 0,
    "message": "",
    "user_id": 1574260633,
    "raw_message": "",
}
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


@fixture
def msg_factory():
    return MsgCheckerFactory(
        owner=1,
        super_users=[2, 3],
        white_users=[4],
        black_users=[5],
        white_groups=[6, 7],
        fail_cb=lambda: _CB_BUF.put(True),
    )


def priv_e(uid: int):
    e = event.PrivateMessageEvent(**_PRIVATE_EVENT_DICT)
    e.sender.user_id = e.user_id = uid
    return e


def group_e(uid: int, gid: int, role: str = "member"):
    e = event.GroupMessageEvent(**_GRUOP_EVENT_DICT)
    e.group_id = gid
    e.sender.user_id = e.user_id = uid
    e.sender.role = role
    return e


async def test_msg_checker(msg_factory: MsgCheckerFactory):
    c1 = msg_factory.get_base(LevelRole.NORMAL)
    assert await c1.check(priv_e(1))
    assert await c1.check(priv_e(3))
    assert await c1.check(priv_e(4))
    assert not await c1.check(priv_e(5))
    _CB_BUF.get_nowait()
    assert await c1.check(priv_e(10))
    assert await c1.check(group_e(2, 6))

    c2 = msg_factory.get_base(LevelRole.WHITE)
    assert not await c2.check(priv_e(10))
    _CB_BUF.get_nowait()

    c3 = msg_factory.get_private(LevelRole.NORMAL)
    assert await c3.check(priv_e(1))
    assert not await c3.check(group_e(1, 6))
    _CB_BUF.get_nowait()

    c4 = msg_factory.get_group(LevelRole.NORMAL)
    assert not await c4.check(priv_e(1))
    _CB_BUF.get_nowait()
    assert await c4.check(group_e(1, 6))
    assert not await c4.check(group_e(1, 8))
    _CB_BUF.get_nowait()

    c5 = msg_factory.get_base(LevelRole.NORMAL, ok_cb=lambda: _CB_BUF.put(True))
    assert await c5.check(priv_e(1))
    _CB_BUF.get_nowait()

    c6 = msg_factory.get_base(GroupRole.OWNER)
    assert not await c6.check(priv_e(1))
    _CB_BUF.get_nowait()
    assert await c6.check(group_e(1, 6, "owner"))
    assert not await c6.check(group_e(1, 6, "admin"))
    _CB_BUF.get_nowait()
    assert not await c6.check(group_e(1, 6, "member"))
    _CB_BUF.get_nowait()

    c7 = msg_factory.get_base(GroupRole.ADMIN)
    c8 = msg_factory.get_base(LevelRole.WHITE)
    assert await (c7 & c8).check(group_e(4, 6, "admin"))


def at_e(atid: int | str):
    e = priv_e(1)
    e.raw_message = f"[CQ:at,qq={atid}]"
    e.message.append(AtSegment(atid))
    return e


async def test_at_checker():
    c1 = AtMsgChecker(1)
    assert await c1.check(at_e(1))
    assert not await c1.check(at_e(2))

    c2 = AtMsgChecker("all")
    assert not await c2.check(at_e(1))
    assert await c2.check(at_e("all"))

    c3 = AtMsgChecker()
    assert await c3.check(at_e(1))
    assert await c3.check(at_e(2))
