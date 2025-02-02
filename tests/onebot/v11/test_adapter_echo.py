from melobot.protocols.onebot.v11.adapter import echo
from melobot.protocols.onebot.v11.const import ACTION_TYPE_KEY_NAME
from tests.base import *


def head() -> dict:
    return {"status": "ok", "retcode": 0}


def ec(**kv_pairs):
    return head() | {"data": kv_pairs if len(kv_pairs) else None}


def fake_ec(**kv_pairs):
    return ec(**kv_pairs) | {"action_type": ""}


def li_ec(lis):
    return head() | {"data": lis}


def fake_li_ec(lis):
    return li_ec(lis) | {"action_type": ""}


async def test_empty():
    echo.EmptyEcho(**ec(), action_type="")


async def test_other():
    assert isinstance(
        echo.Echo.resolve({**ec(message_id=123), ACTION_TYPE_KEY_NAME: "send_msg"}),
        echo.SendMsgEcho,
    )
    assert isinstance(
        echo.Echo.resolve(
            {
                **ec(message_id=123, forward_id="abc"),
                ACTION_TYPE_KEY_NAME: "send_private_forward_msg",
            }
        ),
        echo.SendForwardMsgEcho,
    )

    assert echo.Echo.resolve(
        {
            **ec(
                time=123,
                message_type="private",
                message_id=123,
                real_id=456,
                sender={"user_id": 789, "nickname": "melody", "sex": "male", "age": 18},
                message="123&#91;45[CQ:node,user_id=10001000,nickname=某人,content=&#91;CQ:face&#44;id=123&#93;哈喽～]12345",
            ),
            ACTION_TYPE_KEY_NAME: "get_msg",
        }
    ).data["message"][0].data == {"text": "123[45"}

    assert not (
        echo.GetMsgEcho(
            **fake_ec(
                time=123,
                message_type="private",
                message_id=123,
                real_id=456,
                sender={
                    "user_id": 789,
                    "nickname": "melody",
                    "sex": "male",
                    "age": 18,
                },
                message=[
                    {"type": "text", "data": {"text": "12345"}},
                    {
                        "type": "node",
                        "data": {
                            "user_id": "10001000",
                            "nickname": "某人",
                            "content": [
                                {"type": "face", "data": {"id": "123"}},
                                {"type": "text", "data": {"text": "哈喽～"}},
                            ],
                        },
                    },
                ],
            ),
        )
        .data["sender"]
        .is_group_admin()
    )

    assert (
        echo.GetForwardMsgEcho(
            **fake_ec(
                message=[
                    {
                        "type": "node",
                        "data": {
                            "user_id": "10001000",
                            "nickname": "某人",
                            "content": [
                                {"type": "face", "data": {"id": "123"}},
                                {"type": "text", "data": {"text": "哈喽～"}},
                            ],
                        },
                    }
                ]
            )
        )
        .data["message"][0]
        .data["content"][0]
        .data["id"]
        == 123
    )

    echo.GetLoginInfoEcho(**fake_ec(user_id=123, nickname="melody"))
    echo.GetStrangerInfoEcho(
        **fake_ec(user_id=123, nickname="melody", sex="male", age=18)
    )
    echo.GetFriendListEcho(
        **fake_li_ec(
            [
                {"user_id": 123, "nickname": "melody", "remark": "123"},
                {"user_id": 456, "nickname": "jack", "remark": "123456"},
            ]
        )
    )
    echo.GetGroupInfoEcho(
        **fake_ec(group_id=123, group_name="test", member_count=12, max_member_count=100)
    )
    echo.GetGroupListEcho(
        **fake_li_ec(
            [
                {
                    "group_id": 123,
                    "group_name": "test",
                    "member_count": 12,
                    "max_member_count": 100,
                },
                {
                    "group_id": 123,
                    "group_name": "test",
                    "member_count": 12,
                    "max_member_count": 100,
                },
            ]
        )
    )

    base_info = {
        "group_id": 123,
        "user_id": 123,
        "nickname": "melody",
        "card": "123",
        "sex": "male",
        "age": 18,
        "area": "123",
        "join_time": 1234567,
        "last_sent_time": 1234567890,
        "level": "123",
        "role": "admin",
        "unfriendly": False,
        "title": "hello world",
        "title_expire_time": 1234567890,
        "card_changeable": True,
    }
    echo.GetGroupMemberInfoEcho(**fake_ec(**base_info))
    echo.GetGroupMemberListEcho(**fake_li_ec([base_info, base_info]))

    base_info = {
        "user_id": 123,
        "nickname": "melody",
        "avatar": "123",
        "description": "123",
    }
    echo.GetGroupHonorInfoEcho(
        **fake_ec(
            group_id=123,
            current_talkative={
                "user_id": 123,
                "nickname": "melody",
                "avatar": "123",
                "day_count": 123,
            },
            talkative_list=[base_info],
            performer_list=[base_info],
            legend_list=[base_info],
            strong_newbie_list=[base_info],
            emotion_list=[base_info],
        )
    )

    echo.GetCookiesEcho(**fake_ec(cookies="abc123"))
    echo.GetCsrfTokenEcho(**fake_ec(token=123))
    echo.GetCredentialsEcho(**fake_ec(csrf_token=123, cookies="abc123"))
    echo.GetRecordEcho(**fake_ec(file="123"))
    echo.GetImageEcho(**fake_ec(file="123"))
    echo.CanSendRecordEcho(**fake_ec(yes=True))
    echo.CanSendImageEcho(**fake_ec(yes=False))
    assert echo.GetStatusEcho(**fake_ec(online=True, good=True, nice=True)).data["nice"]
    assert (
        echo.GetVersionInfoEcho(
            **fake_ec(
                app_name="lgr",
                app_version="1.0.0",
                platform="linux",
                os_version="1.0.0",
                protocol_version="1.0.0",
            )
        ).data["os_version"]
        == "1.0.0"
    )
