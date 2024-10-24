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
        #: 时间戳
        self.time: int

        super().__init__(self._model.time, protocol=PROTOCOL_IDENTIFIER)
        #: 自身ID
        self.self_id: int = self._model.self_id
        #: 事件类型
        self.post_type: Literal["message", "notice", "request", "meta_event"] | str = (
            self._model.post_type
        )
        #: 事件原始数据
        self.raw: dict[str, Any] = event_data

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
        #: 消息内容（消息段表示）
        self.message: list[Segment]
        #: 消息发送者
        self.sender: _MessageSender | _GroupMessageSender
        #: 消息内容（通用内容表示）
        self.contents: Sequence[content.Content] = []
        #: 消息内容（cq 字符串表示）
        self.raw_message: str

        data = event_data
        if isinstance(data["message"], str):
            self.message = Segment.resolve_cq(data["raw_message"])
        else:
            self.message = [
                Segment.resolve(dic["type"], dic["data"]) for dic in data["message"]
            ]
        self.contents = segs_to_contents(self.message)

        #: 消息类型
        self.message_type: Literal["private", "group"] | str = self._model.message_type
        #: 消息子类型
        self.sub_type: (
            Literal[
                "friend", "group", "other", "normal", "anonymous", "notice", "group_self"
            ]
            | str
        ) = self._model.sub_type
        #: 消息 id
        self.message_id: int = self._model.message_id
        #: 消息发送者 ID
        self.user_id: int = self._model.user_id
        self.raw_message = self._model.raw_message
        #: 消息字体
        self.font: int = self._model.font

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

        #: 发送者 ID
        self.user_id: int | None = self._model.user_id
        #: 发送者昵称
        self.nickname: str | None = self._model.nickname
        #: 发送者性别
        self.sex: Literal["male", "female", "unknown"] | None = self._model.sex
        #: 发送者年龄
        self.age: int | None = self._model.age

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

        #: 消息发送者
        self.sender: _MessageSender
        self.sender = _MessageSender(**event_data["sender"])

        self._model: PrivateMessageEvent.Model
        #: 消息类型
        self.message_type: Literal["private"]
        # 消息子类型
        self.sub_type: Literal["friend", "group", "other"]


class _MessageAnonymous:

    class Model(BaseModel):
        id: int
        name: str
        flag: str

    def __init__(self, **anonymous_data: Any) -> None:
        self._model = self.Model(**anonymous_data)

        #: 匿名信息的 id
        self.id: int = self._model.id
        #: 匿名信息的 name
        self.name: str = self._model.name
        #: 匿名信息的 flag
        self.flag: str = self._model.flag


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

        #: 发送者头衔
        self.card: str | None = self._model.card
        #: 发送者地区
        self.area: str | None = self._model.area
        #: 发送者等级
        self.level: str | None = self._model.level
        #: 发送者角色
        self.role: Literal["owner", "admin", "member"] | None = self._model.role
        #: 发送者群昵称
        self.title: str | None = self._model.title


class GroupMessageEvent(MessageEvent):

    class Model(MessageEvent.Model):
        message_type: Literal["group"]
        sub_type: Literal["normal", "anonymous", "notice", "group_self"] | str
        group_id: int

    def __init__(self, **event_data: Any) -> None:
        super().__init__(**event_data)

        #: 消息发送者
        self.sender: _GroupMessageSender
        self.sender = _GroupMessageSender(**event_data["sender"])
        #: 消息匿名信息段
        self.anonymous: _MessageAnonymous | None = (
            _MessageAnonymous(**event_data["anonymous"])
            if event_data["anonymous"]
            else None
        )
        #: 消息来源群号
        self.group_id: int = self._model.group_id

        self._model: GroupMessageEvent.Model
        #: 消息类型
        self.message_type: Literal["group"]
        #: 消息子类型
        self.sub_type: Literal["normal", "anonymous", "notice", "group_self"]


class MetaEvent(Event):

    class Model(Event.Model):
        post_type: Literal["meta_event"]
        meta_event_type: Literal["lifecycle", "heartbeat"] | str

    def __init__(self, **event_data: Any) -> None:
        super().__init__(**event_data)

        self._model: MetaEvent.Model
        #: 元事件类型
        self.meta_event_type: Literal["lifecycle", "heartbeat"] | str = (
            self._model.meta_event_type
        )

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
        #: 元事件类型
        self.meta_event_type: Literal["lifecycle"]
        #: 元事件子类型
        self.sub_type: Literal["enable", "disable", "connect"] | str = (
            self._model.sub_type
        )

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

        #: 心跳元事件在线状态
        self.online: bool | None = self._model.online
        #: 心跳元事件健康状态
        self.good: bool = self._model.good
        #: 心跳元事件原始内容
        self.raw: dict[str, Any] = status_data


class HeartBeatMetaEvent(MetaEvent):

    class Model(MetaEvent.Model):
        meta_event_type: Literal["heartbeat"]
        interval: int

    def __init__(self, **event_data: Any) -> None:
        super().__init__(**event_data)

        self._model: HeartBeatMetaEvent.Model

        #: 元事件类型
        self.meta_event_type: Literal["heartbeat"]
        #: 心跳元事件状态
        self.status: _MetaHeartBeatStatus = _MetaHeartBeatStatus(**event_data["status"])
        #: 心跳间隔
        self.interval: int = self._model.interval


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
        #: 通知事件类型
        self.notice_type: (
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
        ) = self._model.notice_type

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
        """是否是群文件上传通知事件"""
        return self.notice_type == "group_upload"

    def is_group_admin(self) -> bool:
        """是否是群管理员变动通知事件"""
        return self.notice_type == "group_admin"

    def is_group_decrease(self) -> bool:
        """是否是群成员减少通知事件"""
        return self.notice_type == "group_decrease"

    def is_group_increase(self) -> bool:
        """是否是群成员增加通知事件"""
        return self.notice_type == "group_increase"

    def is_group_ban(self) -> bool:
        """是否是群禁言通知事件"""
        return self.notice_type == "group_ban"

    def is_friend_add(self) -> bool:
        """是否是好友添加事件"""
        return self.notice_type == "friend_add"

    def is_group_recall(self) -> bool:
        """是否是群消息撤回事件"""
        return self.notice_type == "group_recall"

    def is_friend_recall(self) -> bool:
        """是否是私聊消息撤回事件"""
        return self.notice_type == "friend_recall"

    def is_notify(self) -> bool:
        """是否是 notify 类型通知事件"""
        return self.notice_type == "notify"


class _GroupUploadFile:

    class Model(BaseModel):
        id: str
        name: str
        size: int
        busid: int

    def __init__(self, **file_data: Any) -> None:
        self._model = self.Model(**file_data)

        #: 群文件 id
        self.id: str = self._model.id
        #: 群文件名称
        self.name: str = self._model.name
        #: 群文件大小
        self.size: int = self._model.size
        #: 群文件 busid
        self.busid: int = self._model.busid


class GroupUploadNoticeEvent(NoticeEvent):

    class Model(NoticeEvent.Model):
        notice_type: Literal["group_upload"]
        group_id: int
        user_id: int

    def __init__(self, **event_data: Any) -> None:
        super().__init__(**event_data)

        self._model: GroupUploadNoticeEvent.Model

        #: 通知事件类型
        self.notice_type: Literal["group_upload"]
        #: 群号
        self.group_id: int = self._model.group_id
        #: 事件主体人 qq 号
        self.user_id: int = self._model.user_id
        #: 文件描述对象
        self.file: _GroupUploadFile = _GroupUploadFile(**event_data["file"])


class GroupAdminNoticeEvent(NoticeEvent):

    class Model(NoticeEvent.Model):
        notice_type: Literal["group_admin"]
        sub_type: Literal["set", "unset"]
        group_id: int
        user_id: int

    def __init__(self, **event_data: Any) -> None:
        super().__init__(**event_data)

        self._model: GroupAdminNoticeEvent.Model

        #: 通知事件类型
        self.notice_type: Literal["group_admin"]
        #: 子类型
        self.sub_type: Literal["set", "unset"] = self._model.sub_type
        #: 群号
        self.group_id: int = self._model.group_id
        #: 事件主体人 qq 号
        self.user_id: int = self._model.user_id

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

        #: 通知事件类型
        self.notice_type: Literal["group_decrease"]
        #: 子类型
        self.sub_type: Literal["kick", "leave", "kick_me"] = self._model.sub_type
        #: 群号
        self.group_id: int = self._model.group_id
        #: 操作者 qq 号
        self.operator_id: int = self._model.operator_id
        #: 事件主体人 qq 号
        self.user_id: int = self._model.user_id

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

        #: 通知事件类型
        self.notice_type: Literal["group_increase"]
        #: 子类型
        self.sub_type: Literal["invite", "approve"] = self._model.sub_type
        #: 群号
        self.group_id: int = self._model.group_id
        #: 操作者 qq 号
        self.operator_id: int = self._model.operator_id
        #: 事件主体人 qq 号
        self.user_id: int = self._model.user_id

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

        #: 通知事件类型
        self.notice_type: Literal["group_ban"]
        #: 子类型
        self.sub_type: Literal["ban", "lift_ban"] = self._model.sub_type
        #: 群号
        self.group_id: int = self._model.group_id
        #: 操作者 qq 号
        self.operator_id: int = self._model.operator_id
        #: 事件主体人 qq 号
        self.user_id: int = self._model.user_id
        #: 禁言间隔
        self.duration: int = self._model.duration

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

        #: 通知事件类型
        self.notice_type: Literal["friend_add"]
        #: 事件主体人 qq 号
        self.user_id: int = self._model.user_id


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

        #: 通知事件类型
        self.notice_type: Literal["group_recall"]
        #: 群号
        self.group_id: int = self._model.group_id
        #: 事件主体人 qq 号
        self.user_id: int = self._model.user_id
        #: 操作者 qq 号
        self.operator_id: int = self._model.operator_id
        #: 被撤回的消息 id
        self.message_id: int = self._model.message_id


class FriendRecallNoticeEvent(NoticeEvent):

    class Model(NoticeEvent.Model):
        notice_type: Literal["friend_recall"]
        user_id: int
        message_id: int

    def __init__(self, **event_data: Any) -> None:
        super().__init__(**event_data)

        self._model: FriendRecallNoticeEvent.Model

        #: 通知事件类型
        self.notice_type: Literal["friend_recall"]
        #: 事件主体人 qq 号
        self.user_id: int = self._model.user_id
        #: 被撤回的消息 id
        self.message_id: int = self._model.message_id


class NotifyNoticeEvent(NoticeEvent):

    class Model(NoticeEvent.Model):
        notice_type: Literal["notify"]
        sub_type: Literal["poke", "lucky_king", "honor"] | str

    def __init__(self, **event_data: Any) -> None:
        super().__init__(**event_data)

        self._model: NotifyNoticeEvent.Model

        #: 通知事件类型
        self.notice_type: Literal["notify"]
        #: 子类型
        self.sub_type: Literal["poke", "lucky_king", "honor"] | str = self._model.sub_type

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
        group_id: int | None = None
        user_id: int
        target_id: int

    def __init__(self, **event_data: Any) -> None:
        super().__init__(**event_data)

        self._model: PokeNotifyEvent.Model
        #: 子类型
        self.sub_type: Literal["poke"]
        #: 群号
        self.group_id: int | None = self._model.group_id
        #: 事件发起者 qq 号
        self.user_id: int = self._model.user_id
        #: 事件作用者 qq 号
        self.target_id: int = self._model.target_id


class LuckyKingNotifyEvent(NotifyNoticeEvent):

    class Model(NotifyNoticeEvent.Model):
        sub_type: Literal["lucky_king"]
        group_id: int
        user_id: int
        target_id: int

    def __init__(self, **event_data: Any) -> None:
        super().__init__(**event_data)

        self._model: LuckyKingNotifyEvent.Model

        #: 子类型
        self.sub_type: Literal["lucky_king"]
        #: 群号
        self.group_id: int = self._model.group_id
        #: 红包发送者 qq 号
        self.user_id: int = self._model.user_id
        #: 运气王 qq 号
        self.target_id: int = self._model.target_id


class HonorNotifyEvent(NotifyNoticeEvent):

    class Model(NotifyNoticeEvent.Model):
        sub_type: Literal["honor"]
        group_id: int
        honor_type: Literal["talkative", "performer", "emotion"]
        user_id: int

    def __init__(self, **event_data: Any) -> None:
        super().__init__(**event_data)

        self._model: HonorNotifyEvent.Model

        #: 子类型
        self.sub_type: Literal["honor"]
        #: 群号
        self.group_id: int = self._model.group_id
        #: 群荣誉类型
        self.honor_type: Literal["talkative", "performer", "emotion"] = (
            self._model.honor_type
        )
        #: 事件主体人 qq 号
        self.user_id: int = self._model.user_id

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
        #: 请求事件类型
        self.request_type: Literal["friend", "group"] | str = self._model.request_type

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

        #: 请求事件类型
        self.request_type: Literal["friend"]
        #: 请求人 qq 号
        self.user_id: int = self._model.user_id
        #: 加好友备注
        self.comment: str = self._model.comment
        #: 请求 flag，在调用处理请求的 API 时需要传入
        self.flag: str = self._model.flag


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
        #: 请求事件类型
        self.request_type: Literal["group"]
        #: 子类型
        self.sub_type: str = self._model.sub_type
        #: 群号
        self.group_id: int = self._model.group_id
        #: 请求人 qq 号
        self.user_id: int = self._model.user_id
        #: 加群备注
        self.comment: str = self._model.comment
        #: 请求 flag，在调用处理请求的 API 时需要传入
        self.flag: str = self._model.flag

    def is_add(self) -> bool:
        return self.sub_type == "add"

    def is_invite(self) -> bool:
        return self.sub_type == "invite"
