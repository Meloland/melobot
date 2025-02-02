import json

from typing_extensions import Any, Iterable, Literal, Optional, TypedDict

from melobot.adapter import Action as RootAction
from melobot.handle import try_get_event

from ..const import PROTOCOL_IDENTIFIER
from .segment import NodeSegment, Segment, TextSegment


class Action(RootAction):
    def __init__(self, type: str, params: dict[str, Any]) -> None:
        self.time: int

        super().__init__(protocol=PROTOCOL_IDENTIFIER, trigger=try_get_event())

        self.type = type
        self.params = params
        self.need_echo = False

    def set_echo(self, status: bool) -> None:
        self.need_echo = status

    def extract(self) -> dict[str, Any]:
        obj = {
            "action": self.type,
            "params": self.params,
        }
        if self.need_echo:
            obj["echo"] = self.id
        return obj

    def flatten(self) -> str:
        return json.dumps(self.extract(), ensure_ascii=False)


def msgs_to_dicts(
    msgs: str | Segment | Iterable[Segment] | dict | Iterable[dict],
) -> list[dict]:
    if isinstance(msgs, str):
        return [TextSegment(msgs).to_dict(force_str=True)]
    if isinstance(msgs, Segment):
        return [msgs.to_dict(force_str=True)]
    if isinstance(msgs, dict):
        return [msgs]

    return [
        msg.to_dict(force_str=True) if isinstance(msg, Segment) else msg for msg in msgs
    ]


class SendMsgAction(Action):
    def __init__(
        self,
        msgs: str | Segment | Iterable[Segment] | dict | Iterable[dict],
        user_id: Optional[int] = None,
        group_id: Optional[int] = None,
    ) -> None:
        type = "send_msg"
        _msgs = msgs_to_dicts(msgs)
        if group_id is None:
            assert user_id is not None
            params = {
                "message_type": "private",
                "user_id": user_id,
                "message": _msgs,
                "auto_escape": False,
            }
        else:
            params = {
                "message_type": "group",
                "group_id": group_id,
                "message": _msgs,
                "auto_escape": False,
            }
        super().__init__(type, params)


class SendForwardMsgAction(Action):
    def __init__(
        self,
        msgs: Iterable[NodeSegment] | Iterable[dict],
        user_id: Optional[int] = None,
        group_id: Optional[int] = None,
    ) -> None:
        _msgs = msgs_to_dicts(msgs)
        if group_id is None:
            type = "send_private_forward_msg"
            params = {"user_id": user_id, "messages": _msgs, "auto_escape": False}
        else:
            type = "send_group_forward_msg"
            params = {"group_id": group_id, "messages": _msgs, "auto_escape": False}
        super().__init__(type, params)


class DeleteMsgAction(Action):
    def __init__(self, msg_id: int) -> None:
        type = "delete_msg"
        params = {
            "message_id": msg_id,
        }
        super().__init__(type, params)


class GetMsgAction(Action):
    def __init__(self, msg_id: int) -> None:
        type = "get_msg"
        params = {"message_id": msg_id}
        super().__init__(type, params)


class GetForwardMsgAction(Action):
    def __init__(self, forward_id: str) -> None:
        type = "get_forward_msg"
        params = {"id": forward_id}
        super().__init__(type, params)


class SendLikeAction(Action):
    def __init__(self, user_id: int, times: int = 1) -> None:
        type = "send_like"
        params = {"user_id": user_id, "times": times}
        super().__init__(type, params)


class SetGroupKickAction(Action):
    def __init__(self, group_id: int, user_id: int, later_reject: bool = False) -> None:
        type = "set_group_kick"
        params = {
            "group_id": group_id,
            "user_id": user_id,
            "reject_add_request": later_reject,
        }
        super().__init__(type, params)


class SetGroupBanAction(Action):
    def __init__(self, group_id: int, user_id: int, duration: int = 30 * 60) -> None:
        type = "set_group_ban"
        params = {
            "group_id": group_id,
            "user_id": user_id,
            "duration": duration,
        }
        super().__init__(type, params)


class SetGroupAnonymousBanAction(Action):

    class AnonymousDict(TypedDict):
        id: int
        name: str
        flag: str

    def __init__(
        self,
        group_id: int,
        anonymous: AnonymousDict,
        anonymous_flag: str,
        duration: int = 30 * 60,
    ) -> None:
        type = "set_group_anonymous_ban"
        params = {
            "group_id": group_id,
            "anonymous": anonymous,
            "anonymous_flag": anonymous_flag,
            "duration": duration,
        }
        super().__init__(type, params)


class SetGroupWholeBanAction(Action):
    def __init__(self, group_id: int, enable: bool = True) -> None:
        type = "set_group_whole_ban"
        params = {"group_id": group_id, "enable": enable}
        super().__init__(type, params)


class SetGroupAdminAction(Action):
    def __init__(self, group_id: int, user_id: int, enable: bool = True) -> None:
        type = "set_group_admin"
        params = {"group_id": group_id, "user_id": user_id, "enable": enable}
        super().__init__(type, params)


class SetGroupAnonymousAction(Action):
    def __init__(self, group_id: int, enable: bool = True) -> None:
        type = "set_group_anonymous"
        params = {"group_id": group_id, "enable": enable}
        super().__init__(type, params)


class SetGroupCardAction(Action):
    def __init__(self, group_id: int, user_id: int, card: str = "") -> None:
        type = "set_group_card"
        params = {"group_id": group_id, "user_id": user_id, "card": card}
        super().__init__(type, params)


class SetGroupNameAction(Action):
    def __init__(self, group_id: int, name: str) -> None:
        type = "set_group_name"
        params = {"group_id": group_id, "group_name": name}
        super().__init__(type, params)


class SetGroupLeaveAction(Action):
    def __init__(self, group_id: int, is_dismiss: bool = False) -> None:
        type = "set_group_leave"
        params = {"group_id": group_id, "is_dismiss": is_dismiss}
        super().__init__(type, params)


class SetGroupSpecialTitleAction(Action):
    def __init__(
        self, group_id: int, user_id: int, title: str = "", duration: int = -1
    ) -> None:
        type = "set_group_special_title"
        params = {
            "group_id": group_id,
            "user_id": user_id,
            "special_title": title,
            "duration": duration,
        }
        super().__init__(type, params)


class SetFriendAddRequestAction(Action):
    def __init__(self, add_flag: str, approve: bool = True, remark: str = "") -> None:
        type = "set_friend_add_request"
        params = {"flag": add_flag, "approve": approve, "remark": remark}
        super().__init__(type, params)


class SetGroupAddRequestAction(Action):
    def __init__(
        self,
        add_flag: str,
        add_type: Literal["add", "invite"],
        approve: bool = True,
        reason: str = "",
    ) -> None:
        type = "set_group_add_request"
        params = {
            "flag": add_flag,
            "sub_type": add_type,
            "approve": approve,
        }
        if reason:
            self.params["reason"] = reason
        super().__init__(type, params)


class GetLoginInfoAction(Action):
    def __init__(self) -> None:
        type = "get_login_info"
        params: dict = {}
        super().__init__(type, params)


class GetStrangerInfoAction(Action):
    def __init__(self, user_id: int, no_cache: bool = False) -> None:
        type = "get_stranger_info"
        params = {"user_id": user_id, "no_cache": no_cache}
        super().__init__(type, params)


class GetFriendlistAction(Action):
    def __init__(self) -> None:
        type = "get_friend_list"
        params: dict = {}
        super().__init__(type, params)


class GetGroupInfoAction(Action):
    def __init__(self, group_id: int, no_cache: bool = False) -> None:
        type = "get_group_info"
        params = {"group_id": group_id, "no_cache": no_cache}
        super().__init__(type, params)


class GetGrouplistAction(Action):
    def __init__(self) -> None:
        type = "get_group_list"
        params: dict = {}
        super().__init__(type, params)


class GetGroupMemberInfoAction(Action):
    def __init__(self, group_id: int, user_id: int, no_cache: bool = False) -> None:
        type = "get_group_member_info"
        params = {"group_id": group_id, "user_id": user_id, "no_cache": no_cache}
        super().__init__(type, params)


class GetGroupMemberlistAction(Action):
    def __init__(self, group_id: int) -> None:
        type = "get_group_member_list"
        params = {"group_id": group_id}
        super().__init__(type, params)


class GetGroupHonorInfoAction(Action):
    def __init__(
        self,
        group_id: int,
        type: Literal[
            "talkative", "performer", "legend", "strong_newbie", "emotion", "all"
        ],
    ) -> None:
        _type = "get_group_honor_info"
        params = {"group_id": group_id, "type": type}
        super().__init__(_type, params)


class GetCookiesAction(Action):
    def __init__(self, domain: str = "") -> None:
        type = "get_cookies"
        params = {"domain": domain}
        super().__init__(type, params)


class GetCsrfTokenAction(Action):
    def __init__(self) -> None:
        type = "get_csrf_token"
        params: dict = {}
        super().__init__(type, params)


class GetCredentialsAction(Action):
    def __init__(self, domain: str = "") -> None:
        type = "get_credentials"
        params = {"domain": domain}
        super().__init__(type, params)


class GetRecordAction(Action):
    def __init__(self, file: str, out_format: str) -> None:
        type = "get_record"
        params = {"file": file, "out_format": out_format}
        super().__init__(type, params)


class GetImageAction(Action):
    def __init__(self, file: str) -> None:
        type = "get_image"
        params = {"file": file}
        super().__init__(type, params)


class CanSendImageAction(Action):
    def __init__(self) -> None:
        type = "can_send_image"
        params: dict = {}
        super().__init__(type, params)


class CanSendRecordAction(Action):
    def __init__(self) -> None:
        type = "can_send_record"
        params: dict = {}
        super().__init__(type, params)


class GetStatusAction(Action):
    def __init__(self) -> None:
        type = "get_status"
        params: dict = {}
        super().__init__(type, params)


class GetVersionInfoAction(Action):
    def __init__(self) -> None:
        type = "get_version_info"
        params: dict = {}
        super().__init__(type, params)


class SetRestartAction(Action):
    def __init__(self, delay: int = 0) -> None:
        type = "set_restart"
        params = {"delay": delay}
        super().__init__(type, params)


class CleanCacheAction(Action):
    def __init__(self) -> None:
        type = "clean_cache"
        params: dict = {}
        super().__init__(type, params)
