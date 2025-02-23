from typing import cast

from melobot.adapter.content import TextContent
from melobot.protocols.onebot.v11.adapter import event
from tests.base import *


@fixture
def base_head():
    return {"time": 1725292489, "self_id": 123456}


@fixture
def msg_head(base_head):
    return base_head | {"post_type": "message"}


@fixture
def private_sender():
    return {
        "age": 0,
        "nickname": "这是一个群昵称",
        "sex": "unknown",
        "user_id": 1574260633,
    }


@fixture
def group_sender(private_sender):
    return private_sender | {
        "area": "",
        "card": "",
        "level": "",
        "role": "member",
        "title": "",
    }


async def test_msg(msg_head, private_sender, group_sender) -> None:
    e1 = event.Event.resolve(
        msg_head
        | {
            "message_type": "group",
            "sub_type": "normal",
            "sender": group_sender,
            "message_id": -1234567890,
            "font": 0,
            "message": "123456",
            "user_id": 1574260633,
            "anonymous": None,
            "group_id": 535705163,
            "raw_message": "123456",
        }
    )
    assert cast(TextContent, e1.contents[0]).text == "123456"

    e2 = event.Event.resolve(
        msg_head
        | {
            "message_type": "group",
            "sub_type": "anonymous",
            "sender": group_sender,
            "message_id": -1234567890,
            "font": 0,
            "message": "",
            "user_id": 1574260633,
            "anonymous": {"id": 123, "name": "test", "flag": "adjfajklj12j32l"},
            "group_id": 535705163,
            "raw_message": "",
        }
    )
    e3 = event.Event.resolve(
        msg_head
        | {
            "message_type": "group",
            "sub_type": "notice",
            "sender": group_sender,
            "message_id": -1234567890,
            "font": 0,
            "message": "",
            "user_id": 1574260633,
            "anonymous": None,
            "group_id": 535705163,
            "raw_message": "",
        }
    )
    e4 = event.Event.resolve(
        msg_head
        | {
            "message_type": "group",
            "sub_type": "group_self",
            "sender": group_sender,
            "message_id": -1234567890,
            "font": 0,
            "message": "",
            "user_id": 1574260633,
            "anonymous": None,
            "group_id": 535705163,
            "raw_message": "",
        }
    )
    e5 = event.Event.resolve(
        msg_head
        | {
            "message_type": "private",
            "sub_type": "friend",
            "sender": private_sender,
            "message_id": -1234567890,
            "font": 0,
            "message": "",
            "user_id": 1574260633,
            "raw_message": "",
        }
    )
    e6 = event.Event.resolve(
        msg_head
        | {
            "message_type": "private",
            "sub_type": "group",
            "sender": private_sender,
            "message_id": -1234567890,
            "font": 0,
            "message": "",
            "user_id": 1574260633,
            "raw_message": "",
        }
    )
    e7 = event.Event.resolve(
        msg_head
        | {
            "message_type": "private",
            "sub_type": "other",
            "sender": private_sender,
            "message_id": -1234567890,
            "font": 0,
            "message": "",
            "user_id": 1574260633,
            "raw_message": "",
        }
    )
    assert isinstance(e1, event.GroupMessageEvent)
    assert isinstance(e2, event.GroupMessageEvent)
    assert isinstance(e3, event.GroupMessageEvent)
    assert isinstance(e4, event.GroupMessageEvent)
    assert isinstance(e5, event.PrivateMessageEvent)
    assert isinstance(e6, event.PrivateMessageEvent)
    assert isinstance(e7, event.PrivateMessageEvent)


@fixture
def meta_head(base_head):
    return base_head | {"post_type": "meta_event"}


@fixture
def lifecycle_head(meta_head):
    return meta_head | {"meta_event_type": "lifecycle"}


async def test_meta(meta_head, lifecycle_head) -> None:
    e1 = event.Event.resolve(lifecycle_head | {"sub_type": "enable"})
    e2 = event.Event.resolve(lifecycle_head | {"sub_type": "disable"})
    e3 = event.Event.resolve(lifecycle_head | {"sub_type": "connect"})
    e4 = event.Event.resolve(
        meta_head
        | {
            "meta_event_type": "heartbeat",
            "status": {"online": True, "good": True},
            "interval": 5000,
        }
    )
    assert isinstance(e1, event.LifeCycleMetaEvent)
    assert isinstance(e2, event.LifeCycleMetaEvent)
    assert isinstance(e3, event.LifeCycleMetaEvent)
    assert isinstance(e4, event.HeartBeatMetaEvent)


@fixture
def notice_head(base_head):
    return base_head | {"post_type": "notice"}


@fixture
def notify_head(notice_head):
    return notice_head | {"notice_type": "notify"}


async def test_notice(notice_head, notify_head) -> None:
    e = event.Event.resolve(
        notice_head
        | {
            "notice_type": "group_upload",
            "group_id": 123456,
            "user_id": 123456,
            "file": {"id": "123", "name": "test.jpg", "size": 123456, "busid": -123},
        }
    )
    assert isinstance(e, event.GroupUploadNoticeEvent)

    e1 = event.Event.resolve(
        notice_head
        | {
            "notice_type": "group_admin",
            "sub_type": "set",
            "group_id": 123456,
            "user_id": 123456,
        }
    )
    e2 = event.Event.resolve(
        notice_head
        | {
            "notice_type": "group_admin",
            "sub_type": "unset",
            "group_id": 123456,
            "user_id": 123456,
        }
    )
    assert isinstance(e1, event.GroupAdminNoticeEvent)
    assert isinstance(e2, event.GroupAdminNoticeEvent)

    e1 = event.Event.resolve(
        notice_head
        | {
            "notice_type": "group_decrease",
            "sub_type": "kick",
            "group_id": 123456,
            "user_id": 123456,
            "operator_id": 123456,
        }
    )
    e2 = event.Event.resolve(
        notice_head
        | {
            "notice_type": "group_decrease",
            "sub_type": "kick_me",
            "group_id": 123456,
            "user_id": 123456,
            "operator_id": 123456,
        }
    )
    e3 = event.Event.resolve(
        notice_head
        | {
            "notice_type": "group_decrease",
            "sub_type": "leave",
            "group_id": 123456,
            "user_id": 123456,
            "operator_id": 123456,
        }
    )
    assert isinstance(e1, event.GroupDecreaseNoticeEvent)
    assert isinstance(e2, event.GroupDecreaseNoticeEvent)
    assert isinstance(e3, event.GroupDecreaseNoticeEvent)

    e1 = event.Event.resolve(
        notice_head
        | {
            "notice_type": "group_increase",
            "sub_type": "invite",
            "group_id": 123456,
            "user_id": 123456,
            "operator_id": 123456,
        }
    )
    e2 = event.Event.resolve(
        notice_head
        | {
            "notice_type": "group_increase",
            "sub_type": "approve",
            "group_id": 123456,
            "user_id": 123456,
            "operator_id": 123456,
        }
    )
    assert isinstance(e1, event.GroupIncreaseNoticeEvent)
    assert isinstance(e2, event.GroupIncreaseNoticeEvent)

    e1 = event.Event.resolve(
        notice_head
        | {
            "notice_type": "group_ban",
            "sub_type": "ban",
            "group_id": 123456,
            "user_id": 123456,
            "operator_id": 123456,
            "duration": 3600,
        }
    )
    e2 = event.Event.resolve(
        notice_head
        | {
            "notice_type": "group_ban",
            "sub_type": "lift_ban",
            "group_id": 123456,
            "user_id": 123456,
            "operator_id": 123456,
            "duration": 3600,
        }
    )
    assert isinstance(e1, event.GroupBanNoticeEvent)
    assert isinstance(e2, event.GroupBanNoticeEvent)

    e1 = event.Event.resolve(notice_head | {"notice_type": "friend_add", "user_id": 123456})
    assert isinstance(e1, event.FriendAddNoticeEvent)

    e1 = event.Event.resolve(
        notice_head
        | {
            "notice_type": "group_recall",
            "group_id": 123456,
            "user_id": 123456,
            "operator_id": 123456,
            "message_id": -12345678,
        }
    )
    assert isinstance(e1, event.GroupRecallNoticeEvent)

    e1 = event.Event.resolve(
        notice_head | {"notice_type": "friend_recall", "user_id": 123456, "message_id": -12345678}
    )
    assert isinstance(e1, event.FriendRecallNoticeEvent)

    e1 = event.Event.resolve(
        notify_head
        | {
            "sub_type": "poke",
            "group_id": 123456,
            "user_id": 123456,
            "target_id": 123456,
        }
    )
    e2 = event.Event.resolve(
        notify_head
        | {
            "sub_type": "lucky_king",
            "group_id": 123456,
            "user_id": 123456,
            "target_id": 123456,
        }
    )
    e3 = event.Event.resolve(
        notify_head
        | {
            "sub_type": "honor",
            "group_id": 123456,
            "user_id": 123456,
            "honor_type": "talkative",
        }
    )
    e4 = event.Event.resolve(
        notify_head
        | {
            "sub_type": "honor",
            "group_id": 123456,
            "user_id": 123456,
            "honor_type": "performer",
        }
    )
    e5 = event.Event.resolve(
        notify_head
        | {
            "sub_type": "honor",
            "group_id": 123456,
            "user_id": 123456,
            "honor_type": "emotion",
        }
    )
    assert isinstance(e1, event.PokeNotifyEvent)
    assert isinstance(e2, event.LuckyKingNotifyEvent)
    assert isinstance(e3, event.HonorNotifyEvent)
    assert isinstance(e4, event.HonorNotifyEvent)
    assert isinstance(e5, event.HonorNotifyEvent)


@fixture
def request_head(base_head):
    return base_head | {"post_type": "request"}


async def test_request(request_head) -> None:
    e1 = event.Event.resolve(
        request_head
        | {
            "request_type": "friend",
            "user_id": 123456,
            "comment": "I want to add you as my friend",
            "flag": "asdfja78a97a07f",
        }
    )
    e2 = event.Event.resolve(
        request_head
        | {
            "request_type": "group",
            "sub_type": "add",
            "group_id": 123456,
            "user_id": 123456,
            "comment": "I want to join your group",
            "flag": "asdfja78a97a07f",
        }
    )
    e3 = event.Event.resolve(
        request_head
        | {
            "request_type": "group",
            "sub_type": "invite",
            "group_id": 123456,
            "user_id": 123456,
            "comment": "I want to join your group",
            "flag": "asdfja78a97a07f",
        }
    )
    assert isinstance(e1, event.FriendRequestEvent)
    assert isinstance(e2, event.GroupRequestEvent)
