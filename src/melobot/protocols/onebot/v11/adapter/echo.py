from __future__ import annotations

from pydantic import BaseModel
from typing_extensions import Any, Literal, Mapping, TypedDict, cast

from melobot.adapter import Echo as RootEcho

from ..const import ACTION_TYPE_KEY_NAME, PROTOCOL_IDENTIFIER
from .event import _GroupMessageSender, _MessageSender
from .segment import NodeGocqCustomSegment, NodeStdCustomSegment, Segment


class Echo(RootEcho):

    class Model(BaseModel):
        status: Literal["ok", "async", "failed"]
        retcode: int
        data: Mapping[str, Any] | list | None

    def __init__(self, **kv_pairs: Any) -> None:
        self._model = self.Model(**kv_pairs)

        _dic = kv_pairs.copy()
        self.action_type: str = _dic.pop(ACTION_TYPE_KEY_NAME)
        self.raw = _dic

        super().__init__(
            protocol=PROTOCOL_IDENTIFIER,
            ok=self._model.status == "ok",
            status=self._model.retcode,
            data=self._model.data,
        )

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(status={self._model.status},"
            f" retcode={self._model.retcode}, action_type={self.action_type})"
        )

    def is_ok(self) -> bool:
        return self._model.status == "ok"

    def is_async(self) -> bool:
        return self._model.status == "async"

    def is_failed(self) -> bool:
        return self._model.status == "failed"

    @classmethod
    def resolve(cls, raw: dict[str, Any]) -> Echo:
        match raw[ACTION_TYPE_KEY_NAME]:
            case "send_private_msg" | "send_group_msg" | "send_msg":
                return SendMsgEcho(**raw)
            case "send_private_forward_msg" | "send_group_forward_msg":
                return SendForwardMsgEcho(**raw)
            case "get_msg":
                return GetMsgEcho(**raw)
            case "get_forward_msg":
                return GetForwardMsgEcho(**raw)
            case "get_login_info":
                return GetLoginInfoEcho(**raw)
            case "get_stranger_info":
                return GetStrangerInfoEcho(**raw)
            case "get_friend_list":
                return GetFriendListEcho(**raw)
            case "get_group_info":
                return GetGroupInfoEcho(**raw)
            case "get_group_list":
                return GetGroupListEcho(**raw)
            case "get_group_member_info":
                return GetGroupMemberInfoEcho(**raw)
            case "get_group_member_list":
                return GetGroupMemberListEcho(**raw)
            case "get_group_honor_info":
                return GetGroupHonorInfoEcho(**raw)
            case "get_cookies":
                return GetCookiesEcho(**raw)
            case "get_csrf_token":
                return GetCsrfTokenEcho(**raw)
            case "get_credentials":
                return GetCredentialsEcho(**raw)
            case "get_record":
                return GetRecordEcho(**raw)
            case "get_image":
                return GetImageEcho(**raw)
            case "can_send_image":
                return CanSendImageEcho(**raw)
            case "can_send_record":
                return CanSendRecordEcho(**raw)
            case "get_status":
                return GetStatusEcho(**raw)
            case "get_version_info":
                return GetVersionInfoEcho(**raw)
            case (
                "delete_msg"
                | "send_like"
                | "set_group_kick"
                | "set_group_ban"
                | "set_group_anonymous_ban"
                | "set_group_whole_ban"
                | "set_group_admin"
                | "set_group_anonymous"
                | "set_group_card"
                | "set_group_name"
                | "set_group_leave"
                | "set_group_special_title"
                | "set_friend_add_request"
                | "set_group_add_request"
                | "set_restart"
                | "clean_cache"
            ):
                return EmptyEcho(**raw)
            case _:
                return Echo(**raw)


class EmptyEcho(Echo):

    class Model(Echo.Model):
        data: None

    data: None


class _SendMsgEchoData(TypedDict):
    message_id: int


class SendMsgEcho(Echo):

    class Model(Echo.Model):
        data: _SendMsgEchoData | None

    data: _SendMsgEchoData | None


class _SendForwardMsgEchoData(TypedDict):
    message_id: int
    forward_id: str


class SendForwardMsgEcho(Echo):

    class Model(Echo.Model):
        data: _SendForwardMsgEchoData | None

    data: _SendForwardMsgEchoData | None


class _GetMsgEchoData(TypedDict):
    time: int
    message_type: Literal["private", "group"]
    message_id: int
    real_id: int


class _GetMsgEchoDataInterface(_GetMsgEchoData):
    sender: _MessageSender | _GroupMessageSender
    message: list[Segment]


class GetMsgEcho(Echo):

    class Model(Echo.Model):
        data: _GetMsgEchoData | None

    data: _GetMsgEchoDataInterface | None

    def __init__(self, **kv_pairs: Any) -> None:
        super().__init__(**kv_pairs)
        if self.data is None:
            return

        data = kv_pairs["data"]
        msgs = data["message"]
        segs: list[Segment]
        if isinstance(msgs, str):
            segs = Segment.__resolve_cq__(msgs)
        else:
            segs = [Segment.resolve(seg_dic["type"], seg_dic["data"]) for seg_dic in msgs]

        sender: _MessageSender | _GroupMessageSender
        if data["message_type"] == "private":
            sender = _MessageSender(**data["sender"])
        else:
            sender = _GroupMessageSender(**data["sender"])

        self.data["message"] = segs
        self.data["sender"] = sender


class _GetForwardMsgEchoData(TypedDict): ...


class _GetForwardMsgEchoDataInterface(_GetForwardMsgEchoData):
    message: list[NodeGocqCustomSegment | NodeStdCustomSegment]


class GetForwardMsgEcho(Echo):

    class Model(Echo.Model):
        data: _GetForwardMsgEchoData | None

    data: _GetForwardMsgEchoDataInterface | None

    def __init__(self, **kv_pairs: Any) -> None:
        super().__init__(**kv_pairs)
        if self.data is None:
            return

        data = kv_pairs["data"]
        msgs = data["message"]
        segs: list[Segment]
        if isinstance(msgs, str):
            segs = Segment.__resolve_cq__(msgs)
        else:
            segs = [Segment.resolve(seg_dic["type"], seg_dic["data"]) for seg_dic in msgs]

        self.data["message"] = cast(list[NodeGocqCustomSegment | NodeStdCustomSegment], segs)


class _GetLoginInfoEchoData(TypedDict):
    user_id: int
    nickname: str


class GetLoginInfoEcho(Echo):

    class Model(Echo.Model):
        data: _GetLoginInfoEchoData | None

    data: _GetLoginInfoEchoData | None


class _GetStrangerInfoEchoData(TypedDict):
    user_id: int
    nickname: str
    sex: Literal["male", "female", "unknown"]
    age: int


class GetStrangerInfoEcho(Echo):

    class Model(Echo.Model):
        data: _GetStrangerInfoEchoData | None

    data: _GetStrangerInfoEchoData | None


class _GetFriendListEchoElem(TypedDict):
    user_id: int
    nickname: str
    remark: str


class GetFriendListEcho(Echo):

    class Model(Echo.Model):
        data: list[_GetFriendListEchoElem] | None

    data: list[_GetFriendListEchoElem] | None


class _GetGroupInfoEchoData(TypedDict):
    group_id: int
    group_name: str
    member_count: int
    max_member_count: int


class GetGroupInfoEcho(Echo):

    class Model(Echo.Model):
        data: _GetGroupInfoEchoData | None

    data: _GetGroupInfoEchoData | None


class GetGroupListEcho(Echo):

    class Model(Echo.Model):
        data: list[_GetGroupInfoEchoData] | None

    data: list[_GetGroupInfoEchoData] | None


class _GetGroupMemberInfoEchoData(TypedDict):
    group_id: int
    user_id: int
    nickname: str
    card: str
    sex: str
    age: int
    area: str
    join_time: int
    last_sent_time: int
    level: str
    role: Literal["owner", "admin", "member"]
    unfriendly: bool
    title: str
    title_expire_time: int
    card_changeable: bool


class GetGroupMemberInfoEcho(Echo):

    class Model(Echo.Model):
        data: _GetGroupMemberInfoEchoData | None

    data: _GetGroupMemberInfoEchoData | None


class GetGroupMemberListEcho(Echo):

    class Model(Echo.Model):
        data: list[_GetGroupMemberInfoEchoData] | None

    data: list[_GetGroupMemberInfoEchoData] | None


class _CurrentTalkativeData(TypedDict):
    user_id: int
    nickname: str
    avatar: str
    day_count: int


class _OtherListData(TypedDict):
    user_id: int
    nickname: str
    avatar: str
    description: str


class _GetGroupHonorInfoEchoData(TypedDict):
    group_id: int
    current_talkative: _CurrentTalkativeData | None
    talkative_list: list[_OtherListData] | None
    performer_list: list[_OtherListData] | None
    legend_list: list[_OtherListData] | None
    strong_newbie_list: list[_OtherListData] | None
    emotion_list: list[_OtherListData] | None


class GetGroupHonorInfoEcho(Echo):

    class Model(Echo.Model):
        data: _GetGroupHonorInfoEchoData | None

    data: _GetGroupHonorInfoEchoData | None


class _GetCookiesEchoData(TypedDict):
    cookies: str


class GetCookiesEcho(Echo):

    class Model(Echo.Model):
        data: _GetCookiesEchoData | None

    data: _GetCookiesEchoData | None


class _GetCsrfTokenEchoData(TypedDict):
    token: int


class GetCsrfTokenEcho(Echo):

    class Model(Echo.Model):
        data: _GetCsrfTokenEchoData | None

    data: _GetCsrfTokenEchoData | None


class _GetCredentialsEchoData(TypedDict):
    cookies: str
    csrf_token: int


class GetCredentialsEcho(Echo):

    class Model(Echo.Model):
        data: _GetCredentialsEchoData | None

    data: _GetCredentialsEchoData | None


class _GetRecordEchoData(TypedDict):
    file: str


class GetRecordEcho(Echo):

    class Model(Echo.Model):
        data: _GetRecordEchoData | None

    data: _GetRecordEchoData | None


class _GetImageEchoData(TypedDict):
    file: str


class GetImageEcho(Echo):

    class Model(Echo.Model):
        data: _GetImageEchoData | None

    data: _GetImageEchoData | None


class _CanSendImageEchoData(TypedDict):
    yes: bool


class CanSendImageEcho(Echo):

    class Model(Echo.Model):
        data: _CanSendImageEchoData | None

    data: _CanSendImageEchoData | None


class _CanSendRecordEchoData(TypedDict):
    yes: bool


class CanSendRecordEcho(Echo):

    class Model(Echo.Model):
        data: _CanSendRecordEchoData | None

    data: _CanSendRecordEchoData | None


class _GetStatusEchoData(TypedDict):
    online: bool
    good: bool


class GetStatusEcho(Echo):

    class Model(Echo.Model):
        data: _GetStatusEchoData | None

    def __init__(self, **kv_pairs: Any) -> None:
        self._model: GetStatusEcho.Model
        super().__init__(**kv_pairs)
        if kv_pairs["data"] is None:
            return

        for k, v in kv_pairs["data"].items():
            if k not in cast(_GetStatusEchoData, self._model.data):
                cast(_GetStatusEchoData, self.data)[k] = v  # type: ignore[literal-required]

    data: _GetStatusEchoData | None


class _GetVersionInfoEchoData(TypedDict):
    app_name: str
    app_version: str
    protocol_version: str


class GetVersionInfoEcho(Echo):

    class Model(Echo.Model):
        data: _GetVersionInfoEchoData | None

    def __init__(self, **kv_pairs: Any) -> None:
        self._model: GetVersionInfoEcho.Model
        super().__init__(**kv_pairs)
        if kv_pairs["data"] is None:
            return

        for k, v in kv_pairs["data"].items():
            if k not in cast(_GetVersionInfoEchoData, self._model.data):
                cast(_GetVersionInfoEchoData, self.data)[k] = v  # type: ignore[literal-required]

    data: _GetVersionInfoEchoData | None
