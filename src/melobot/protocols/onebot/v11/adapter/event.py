from __future__ import annotations

from typing import Any, Literal, Sequence, cast

from pydantic import BaseModel

from melobot.adapter import content
from melobot.adapter.model import Event as RootEvent

from ..const import PROTOCOL_IDENTIFIER
from .segment import Segment, TextSegment, segs_to_contents


class Event(RootEvent):

    class Model(BaseModel):
        time: int
        self_id: int
        post_type: Literal["message", "notice", "request", "meta_event"] | str

    def __init__(self, **event_data: Any) -> None:
        self._model = self.Model(**event_data)
        self.time: int

        super().__init__(self._model.time, protocol=PROTOCOL_IDENTIFIER)
        self.self_id = self._model.self_id
        self.post_type = self._model.post_type

        self.raw = event_data

    @classmethod
    def resolve(cls, event_data: dict[str, Any]) -> Event:
        cls_map: dict[str, type[Event]] = {
            "message": MessageEvent,
            "notice": NoticeEvent,
            "request": RequestEvent,
            "meta_event": MetaEvent,
        }
        if (etype := event_data.get("post_type")) in cls_map:
            return cls_map[etype].resolve(event_data)
        return cls(**event_data)

    def is_message(self) -> bool:
        return self.post_type == "message"

    def is_notice(self) -> bool:
        return self.post_type == "notice"

    def is_request(self) -> bool:
        return self.post_type == "request"

    def is_meta(self) -> bool:
        return self.post_type == "meta_event"


class MessageEvent(Event):

    class Model(Event.Model):
        post_type: Literal["message"]
        message_type: Literal["private", "group"] | str
        sub_type: (
            Literal[
                "friend", "group", "other", "normal", "anonymous", "notice", "group_self"
            ]
            | str
        )
        message_id: int
        user_id: int
        raw_message: str
        font: int

    def __init__(self, **event_data: Any) -> None:
        super().__init__(**event_data)

        self._model: MessageEvent.Model
        self.message: list[Segment]
        self.sender: _MessageSender | _GroupMessageSender
        self.contents: Sequence[content.Content] = []

        data = event_data
        if isinstance(data["message"], str):
            self.message = Segment.resolve_cq(data["raw_message"])
        else:
            self.message = [
                Segment.resolve(dic["type"], dic["data"]) for dic in data["message"]
            ]
        self.contents = segs_to_contents(self.message)

        self.message_type = self._model.message_type
        self.sub_type = self._model.sub_type
        self.message_id = self._model.message_id
        self.user_id = self._model.user_id
        self.raw_message = self._model.raw_message
        self.font = self._model.font

    @classmethod
    def resolve(cls, event_data: dict[str, Any]) -> MessageEvent:
        cls_map: dict[str, type[MessageEvent]] = {
            "private": PrivateMessageEvent,
            "group": GroupMessageEvent,
        }
        if (mtype := event_data.get("message_type")) in cls_map:
            return cls_map[mtype](**event_data)
        return cls(**event_data)

    @property
    def text(self) -> str:
        return "".join(
            seg.data["text"] for seg in self.message if isinstance(seg, TextSegment)
        )

    @property
    def textlines(self) -> str:
        return "\n".join(
            seg.data["text"] for seg in self.message if isinstance(seg, TextSegment)
        )

    def get_segments(self, type: type[Segment] | str) -> list[Segment]:
        if isinstance(type, str):
            return [seg for seg in self.message if seg.type == type]
        return [seg for seg in self.message if isinstance(seg, type)]

    def get_datas(self, type: type[Segment] | str, name: str) -> list[Any]:
        segs = self.get_segments(type)
        return [seg.data.get(name, None) for seg in segs]

    def is_private(self) -> bool:
        """是否为私聊消息（注意群临时会话属于该类别）"""
        return self.message_type == "private" or self.is_private_temp()

    def is_friend(self) -> bool:
        """是否为好友消息"""
        return self.is_private() and self.sub_type == "friend"

    def is_group_temp(self) -> bool:
        """是否为群临时会话（属于私聊的一种）"""
        return self.is_private() and self.sub_type == "group"

    def is_private_other(self) -> bool:
        """是否为其他私聊类型消息"""
        return self.is_private() and self.sub_type == "other"

    def is_private_temp(self) -> bool:
        """是否为临时会话（属于私聊的一种）"""
        return "temp_source" in self.raw

    def is_group(self) -> bool:
        """是否为群消息（正常群消息、群匿名消息、群自身消息、群系统消息属于该类型）"""
        return self.message_type == "group"

    def is_group_normal(self) -> bool:
        """是否为正常群消息"""
        return self.is_group() and self.sub_type == "normal"

    def is_group_self(self) -> bool:
        """是否为群自身消息（即 bot 自己群中发的消息）"""
        return self.is_group() and self.sub_type == "group_self"

    def is_group_anonymous(self) -> bool:
        """是否为匿名群消息"""
        return self.is_group() and self.sub_type == "anonymous"

    def is_group_notice(self) -> bool:
        """是否为群中的\"系统消息\" """
        return self.is_group() and self.sub_type == "notice"


class _MessageSender:

    class Model(BaseModel):
        user_id: int | None = None
        nickname: str | None = None
        sex: Literal["male", "female", "unknown"] | None = None
        age: int | None = None

    def __init__(self, **sender_data: Any) -> None:
        self._model = self.Model(**sender_data)

        self.user_id = self._model.user_id
        self.nickname = self._model.nickname
        self.sex = self._model.sex
        self.age = self._model.age

    def is_group_owner(self) -> bool:
        """判断是否为群主，若不是或不是群类型消息，返回 False"""
        if self.__class__ is not _GroupMessageSender:
            return False

        _self = cast(_GroupMessageSender, self)
        return (
            _self.role is not None and _self.role == "owner"  # pylint: disable=no-member
        )

    def is_group_admin(self) -> bool:
        """判断是否为群管理（包含群主），若不是或不是群类型消息，返回 False"""
        if self.__class__ is not _GroupMessageSender:
            return False

        _self = cast(_GroupMessageSender, self)
        return _self.role is not None and _self.role in (  # pylint: disable=no-member
            "owner",
            "admin",
        )

    def is_group_member_only(self) -> bool:
        """判断是否只是群员（注意只是群员，不包括群主、管理和匿名），若不是或不是群类型消息，返回 False"""
        if self.__class__ is not _GroupMessageSender:
            return False

        _self = cast(_GroupMessageSender, self)
        return (
            _self.role is not None and _self.role == "member"  # pylint: disable=no-member
        )


class PrivateMessageEvent(MessageEvent):

    class Model(MessageEvent.Model):
        message_type: Literal["private"]
        sub_type: Literal["friend", "group", "other"] | str

    def __init__(self, **event_data: Any) -> None:
        super().__init__(**event_data)

        self.sender: _MessageSender
        self.sender = _MessageSender(**event_data["sender"])

        self._model: PrivateMessageEvent.Model
        self.message_type: Literal["private"]
        self.sub_type: Literal["friend", "group", "other"]


class _MessageAnonymous:

    class Model(BaseModel):
        id: int
        name: str
        flag: str

    def __init__(self, **anonymous_data: Any) -> None:
        self._model = self.Model(**anonymous_data)

        self.id = self._model.id
        self.name = self._model.name
        self.flag = self._model.flag


class _GroupMessageSender(_MessageSender):

    class Model(_MessageSender.Model):
        card: str | None = None
        area: str | None = None
        level: str | None = None
        role: Literal["owner", "admin", "member"] | None = None
        title: str | None = None

    def __init__(self, **sender_data: Any) -> None:
        self._model: _GroupMessageSender.Model
        super().__init__(**sender_data)

        self.card = self._model.card
        self.area = self._model.area
        self.level = self._model.level
        self.role = self._model.role
        self.title = self._model.title


class GroupMessageEvent(MessageEvent):

    class Model(MessageEvent.Model):
        message_type: Literal["group"]
        sub_type: Literal["normal", "anonymous", "notice", "group_self"] | str
        group_id: int

    def __init__(self, **event_data: Any) -> None:
        super().__init__(**event_data)

        self.sender: _GroupMessageSender
        self.sender = _GroupMessageSender(**event_data["sender"])
        self.anonymous = (
            _MessageAnonymous(**event_data["anonymous"])
            if event_data["anonymous"]
            else None
        )
        self.group_id = self._model.group_id

        self._model: GroupMessageEvent.Model
        self.message_type: Literal["group"]
        self.sub_type: Literal["normal", "anonymous", "notice", "group_self"]


class MetaEvent(Event):

    class Model(Event.Model):
        post_type: Literal["meta_event"]
        meta_event_type: Literal["lifecycle", "heartbeat"] | str

    def __init__(self, **event_data: Any) -> None:
        super().__init__(**event_data)

        self._model: MetaEvent.Model
        self.meta_event_type = self._model.meta_event_type

    @classmethod
    def resolve(cls, event_data: dict[str, Any]) -> MetaEvent:
        cls_map: dict[str, type[MetaEvent]] = {
            "lifecycle": LifeCycleMetaEvent,
            "heartbeat": HeartBeatMetaEvent,
        }
        if (mtype := event_data.get("meta_event_type")) in cls_map:
            return cls_map[mtype](**event_data)
        return cls(**event_data)

    def is_lifecycle(self) -> bool:
        return self.meta_event_type == "lifecycle"

    def is_heartbeat(self) -> bool:
        return self.meta_event_type == "heartbeat"


class LifeCycleMetaEvent(MetaEvent):

    class Model(MetaEvent.Model):
        meta_event_type: Literal["lifecycle"]
        sub_type: Literal["enable", "disable", "connect"] | str

    def __init__(self, **event_data: Any) -> None:
        super().__init__(**event_data)

        self._model: LifeCycleMetaEvent.Model
        self.meta_event_type: Literal["lifecycle"]
        self.sub_type = self._model.sub_type

    def is_enable(self) -> bool:
        return self.sub_type == "enable"

    def is_disable(self) -> bool:
        return self.sub_type == "disable"

    def is_connect(self) -> bool:
        return self.sub_type == "connect"


class _MetaHeartBeatStatus:

    class Model(BaseModel):
        online: bool | None
        good: bool

    def __init__(self, **status_data: Any) -> None:
        self._model = self.Model(**status_data)

        self.online = self._model.online
        self.good = self._model.good
        self.raw: dict[str, Any] = status_data


class HeartBeatMetaEvent(MetaEvent):

    class Model(MetaEvent.Model):
        meta_event_type: Literal["heartbeat"]
        interval: int

    def __init__(self, **event_data: Any) -> None:
        super().__init__(**event_data)

        self._model: HeartBeatMetaEvent.Model

        self.meta_event_type: Literal["heartbeat"]
        self.status = _MetaHeartBeatStatus(**event_data["status"])
        self.interval = self._model.interval


class NoticeEvent(Event):

    class Model(Event.Model):
        post_type: Literal["notice"]
        notice_type: (
            Literal[
                "group_upload",
                "group_admin",
                "group_decrease",
                "group_increase",
                "group_ban",
                "friend_add",
                "group_recall",
                "friend_recall",
                "notify",
            ]
            | str
        )

    def __init__(self, **event_data: Any) -> None:
        super().__init__(**event_data)

        self._model: NoticeEvent.Model
        self.notice_type = self._model.notice_type

    @classmethod
    def resolve(cls, event_data: dict[str, Any]) -> NoticeEvent:
        cls_map: dict[str, type[NoticeEvent]] = {
            "group_upload": GroupUploadNoticeEvent,
            "group_admin": GroupAdminNoticeEvent,
            "group_decrease": GroupDecreaseNoticeEvent,
            "group_increase": GroupIncreaseNoticeEvent,
            "group_ban": GroupBanNoticeEvent,
            "friend_add": FriendAddNoticeEvent,
            "group_recall": GroupRecallNoticeEvent,
            "friend_recall": FriendRecallNoticeEvent,
        }
        ntype = event_data.get("notice_type")
        if ntype in cls_map:
            return cls_map[ntype](**event_data)
        if ntype == "notify":
            return NotifyNoticeEvent.resolve(event_data)
        return cls(**event_data)

    def is_group_upload(self) -> bool:
        return self.notice_type == "group_upload"

    def is_group_admin(self) -> bool:
        return self.notice_type == "group_admin"

    def is_group_decrease(self) -> bool:
        return self.notice_type == "group_decrease"

    def is_group_increase(self) -> bool:
        return self.notice_type == "group_increase"

    def is_group_ban(self) -> bool:
        return self.notice_type == "group_ban"

    def is_friend_add(self) -> bool:
        return self.notice_type == "friend_add"

    def is_group_recall(self) -> bool:
        return self.notice_type == "group_recall"

    def is_friend_recall(self) -> bool:
        return self.notice_type == "friend_recall"

    def is_notify(self) -> bool:
        return self.notice_type == "notify"


class _GroupUploadFile:

    class Model(BaseModel):
        id: str
        name: str
        size: int
        busid: int

    def __init__(self, **file_data: Any) -> None:
        self._model = self.Model(**file_data)

        self.id = self._model.id
        self.name = self._model.name
        self.size = self._model.size
        self.busid = self._model.busid


class GroupUploadNoticeEvent(NoticeEvent):

    class Model(NoticeEvent.Model):
        notice_type: Literal["group_upload"]
        group_id: int
        user_id: int

    def __init__(self, **event_data: Any) -> None:
        super().__init__(**event_data)

        self._model: GroupUploadNoticeEvent.Model

        self.notice_type: Literal["group_upload"]
        self.group_id = self._model.group_id
        self.user_id = self._model.user_id
        self.file = _GroupUploadFile(**event_data["file"])


class GroupAdminNoticeEvent(NoticeEvent):

    class Model(NoticeEvent.Model):
        notice_type: Literal["group_admin"]
        sub_type: Literal["set", "unset"]
        group_id: int
        user_id: int

    def __init__(self, **event_data: Any) -> None:
        super().__init__(**event_data)

        self._model: GroupAdminNoticeEvent.Model

        self.notice_type: Literal["group_admin"]
        self.sub_type = self._model.sub_type
        self.group_id = self._model.group_id
        self.user_id = self._model.user_id

    def is_set(self) -> bool:
        return self.sub_type == "set"

    def is_unset(self) -> bool:
        return self.sub_type == "unset"


class GroupDecreaseNoticeEvent(NoticeEvent):

    class Model(NoticeEvent.Model):
        notice_type: Literal["group_decrease"]
        sub_type: Literal["kick", "leave", "kick_me"]
        group_id: int
        operator_id: int
        user_id: int

    def __init__(self, **event_data: Any) -> None:
        super().__init__(**event_data)

        self._model: GroupDecreaseNoticeEvent.Model

        self.notice_type: Literal["group_decrease"]
        self.sub_type = self._model.sub_type
        self.group_id = self._model.group_id
        self.operator_id = self._model.operator_id
        self.user_id = self._model.user_id

    def is_kick(self) -> bool:
        return self.sub_type == "kick"

    def is_kick_me(self) -> bool:
        return self.sub_type == "kick_me"

    def is_leave(self) -> bool:
        return self.sub_type == "leave"


class GroupIncreaseNoticeEvent(NoticeEvent):

    class Model(NoticeEvent.Model):
        notice_type: Literal["group_increase"]
        sub_type: Literal["invite", "approve"]
        group_id: int
        operator_id: int
        user_id: int

    def __init__(self, **event_data: Any) -> None:
        super().__init__(**event_data)

        self._model: GroupIncreaseNoticeEvent.Model

        self.notice_type: Literal["group_increase"]
        self.sub_type = self._model.sub_type
        self.group_id = self._model.group_id
        self.operator_id = self._model.operator_id
        self.user_id = self._model.user_id

    def is_invite(self) -> bool:
        return self.sub_type == "invite"

    def is_approve(self) -> bool:
        return self.sub_type == "approve"


class GroupBanNoticeEvent(NoticeEvent):

    class Model(NoticeEvent.Model):
        notice_type: Literal["group_ban"]
        sub_type: Literal["ban", "lift_ban"]
        group_id: int
        operator_id: int
        user_id: int
        duration: int

    def __init__(self, **event_data: Any) -> None:
        super().__init__(**event_data)

        self._model: GroupBanNoticeEvent.Model

        self.notice_type: Literal["group_ban"]
        self.sub_type = self._model.sub_type
        self.group_id = self._model.group_id
        self.operator_id = self._model.operator_id
        self.user_id = self._model.user_id
        self.duration = self._model.duration

    def is_ban(self) -> bool:
        return self.sub_type == "ban"

    def is_lift_ban(self) -> bool:
        return self.sub_type == "lift_ban"


class FriendAddNoticeEvent(NoticeEvent):

    class Model(NoticeEvent.Model):
        notice_type: Literal["friend_add"]
        user_id: int

    def __init__(self, **event_data: Any) -> None:
        super().__init__(**event_data)

        self._model: FriendAddNoticeEvent.Model

        self.notice_type: Literal["friend_add"]
        self.user_id = self._model.user_id


class GroupRecallNoticeEvent(NoticeEvent):

    class Model(NoticeEvent.Model):
        notice_type: Literal["group_recall"]
        group_id: int
        user_id: int
        operator_id: int
        message_id: int

    def __init__(self, **event_data: Any) -> None:
        super().__init__(**event_data)

        self._model: GroupRecallNoticeEvent.Model

        self.notice_type: Literal["group_recall"]
        self.group_id = self._model.group_id
        self.user_id = self._model.user_id
        self.operator_id = self._model.operator_id
        self.message_id = self._model.message_id


class FriendRecallNoticeEvent(NoticeEvent):

    class Model(NoticeEvent.Model):
        notice_type: Literal["friend_recall"]
        user_id: int
        message_id: int

    def __init__(self, **event_data: Any) -> None:
        super().__init__(**event_data)

        self._model: FriendRecallNoticeEvent.Model

        self.notice_type: Literal["friend_recall"]
        self.user_id = self._model.user_id
        self.message_id = self._model.message_id


class NotifyNoticeEvent(NoticeEvent):

    class Model(NoticeEvent.Model):
        notice_type: Literal["notify"]
        sub_type: Literal["poke", "lucky_king", "honor"] | str

    def __init__(self, **event_data: Any) -> None:
        super().__init__(**event_data)

        self._model: NotifyNoticeEvent.Model

        self.notice_type: Literal["notify"]
        self.sub_type = self._model.sub_type

    @classmethod
    def resolve(cls, event_data: dict[str, Any]) -> NotifyNoticeEvent:
        cls_map: dict[str, type[NotifyNoticeEvent]] = {
            "poke": PokeNotifyEvent,
            "lucky_king": LuckyKingNotifyEvent,
            "honor": HonorNotifyEvent,
        }
        if (stype := event_data.get("sub_type")) in cls_map:
            return cls_map[stype](**event_data)
        return cls(**event_data)

    def is_poke(self) -> bool:
        return self.sub_type == "poke"

    def is_lucky_king(self) -> bool:
        return self.sub_type == "lucky_king"

    def is_honor(self) -> bool:
        return self.sub_type == "honor"


class PokeNotifyEvent(NotifyNoticeEvent):

    class Model(NotifyNoticeEvent.Model):
        sub_type: Literal["poke"]
        group_id: int
        user_id: int
        target_id: int

    def __init__(self, **event_data: Any) -> None:
        super().__init__(**event_data)

        self._model: PokeNotifyEvent.Model
        self.sub_type: Literal["poke"]
        self.group_id = self._model.group_id
        self.user_id = self._model.user_id
        self.target_id = self._model.target_id


class LuckyKingNotifyEvent(NotifyNoticeEvent):

    class Model(NotifyNoticeEvent.Model):
        sub_type: Literal["lucky_king"]
        group_id: int
        user_id: int
        target_id: int

    def __init__(self, **event_data: Any) -> None:
        super().__init__(**event_data)

        self._model: LuckyKingNotifyEvent.Model

        self.sub_type: Literal["lucky_king"]
        self.group_id = self._model.group_id
        self.user_id = self._model.user_id
        self.target_id = self._model.target_id


class HonorNotifyEvent(NotifyNoticeEvent):

    class Model(NotifyNoticeEvent.Model):
        sub_type: Literal["honor"]
        group_id: int
        honor_type: Literal["talkative", "performer", "emotion"]
        user_id: int

    def __init__(self, **event_data: Any) -> None:
        super().__init__(**event_data)

        self._model: HonorNotifyEvent.Model

        self.sub_type: Literal["honor"]
        self.group_id = self._model.group_id
        self.honor_type = self._model.honor_type
        self.user_id = self._model.user_id

    def is_talkative(self) -> bool:
        return self.honor_type == "talkative"

    def is_performer(self) -> bool:
        return self.honor_type == "performer"

    def is_emotion(self) -> bool:
        return self.honor_type == "emotion"


class RequestEvent(Event):

    class Model(Event.Model):
        post_type: Literal["request"]
        request_type: Literal["friend", "group"] | str

    def __init__(self, **event_data: Any) -> None:
        super().__init__(**event_data)

        self._model: RequestEvent.Model
        self.request_type = self._model.request_type

    @classmethod
    def resolve(cls, event_data: dict[str, Any]) -> RequestEvent:
        cls_map: dict[str, type[RequestEvent]] = {
            "friend": FriendRequestEvent,
            "group": GroupRequestEvent,
        }
        if (rtype := event_data.get("request_type")) in cls_map:
            return cls_map[rtype](**event_data)
        return cls(**event_data)

    def is_friend(self) -> bool:
        return self.request_type == "friend"

    def is_group(self) -> bool:
        return self.request_type == "group"


class FriendRequestEvent(RequestEvent):

    class Model(RequestEvent.Model):
        request_type: Literal["friend"]
        user_id: int
        comment: str
        flag: str

    def __init__(self, **event_data: Any) -> None:
        super().__init__(**event_data)

        self._model: FriendRequestEvent.Model

        self.request_type: Literal["friend"]
        self.user_id = self._model.user_id
        self.comment = self._model.comment
        self.flag = self._model.flag


class GroupRequestEvent(RequestEvent):

    class Model(RequestEvent.Model):
        request_type: Literal["group"]
        sub_type: Literal["add", "invite"]
        group_id: int
        user_id: int
        comment: str
        flag: str

    def __init__(self, **event_data: Any) -> None:
        super().__init__(**event_data)

        self._model: GroupRequestEvent.Model
        self.request_type: Literal["group"]
        self.sub_type = self._model.sub_type
        self.group_id = self._model.group_id
        self.user_id = self._model.user_id
        self.comment = self._model.comment
        self.flag = self._model.flag

    def is_add(self) -> bool:
        return self.sub_type == "add"

    def is_invite(self) -> bool:
        return self.sub_type == "invite"
