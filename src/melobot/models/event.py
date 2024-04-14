import json
import re
import time

from ..base.abc import BotEvent
from ..base.typing import Any, Callable, Literal, MsgSegment, Optional
from .msg import _get_cq, _get_cq_params, to_cq_arr, to_cq_str


class BotEventBuilder:
    @staticmethod
    def build(rawEvent: dict | str) -> BotEvent:
        if isinstance(rawEvent, str):
            raw: dict[str, str | float | int] = json.loads(rawEvent)
        else:
            raw = rawEvent

        etype = raw.get("post_type")
        if etype in ("message_sent", "message"):
            return MessageEvent(raw)
        elif etype == "request":
            return RequestEvent(raw)
        elif etype == "notice":
            return NoticeEvent(raw)
        elif etype == "meta_event":
            return MetaEvent(raw)
        else:
            return ResponseEvent(raw)


class MessageEvent(BotEvent):
    """消息事件类型

    .. admonition:: 提示
       :class: tip

       一般无需手动实例化该类，多数情况会直接使用本类对象，或将本类用作类型注解。
    """

    def __init__(self, rawEvent: dict) -> None:
        super().__init__(rawEvent)
        #: 收到事件的机器人 qq 号
        self.bot_id: int = rawEvent.get("self_id")  # type: ignore
        #: 消息事件的消息 id
        self.id: int
        #: 消息事件的发送者数据结构
        self.sender: MessageEvent.Sender
        #: 消息事件的来源群号，私聊时此属性也存在并为 :obj:`None`
        self.group_id: Optional[int]
        #: 使用 CQ 字符串表示的，本事件的所有消息内容
        self.raw_content: str
        #: 使用消息段对象列表表示的，本事件的所有消息内容
        self.content: list[MsgSegment]
        #: 本事件的所有消息内容中，纯文本消息的合并字符串
        self.text: str
        #: 消息字体
        self.font: int
        #: 临时消息的来源标记，不是临时消息时为 :obj:`None`
        self.temp_src: Optional[
            Literal[
                "群聊",
                "QQ咨询",
                "查找",
                "QQ电影",
                "热聊",
                "验证消息",
                "多人聊天",
                "约会",
                "通讯录",
            ]
        ]

        self._init()

    @property
    def time(self) -> int:
        """事件发生时刻的时间戳"""
        return self.raw.get("time")  # type: ignore

    @property
    def type(self) -> Literal["message"]:
        """事件的类型（返回指定字面量）"""
        return "message"

    def _init(self) -> None:
        rawEvent = self.raw

        self._cq_regex = re.compile(r"\[CQ:.*?\]")
        self.id = rawEvent["message_id"]
        self.raw_content = self._format_to_str(rawEvent["raw_message"])
        self.content = self._format_to_array(rawEvent["message"])
        self.text = self._get_text(self.content)
        self.font = rawEvent["font"]

        self.temp_src = None
        temp_src = rawEvent.get("temp_source")
        if temp_src:
            self.temp_src = MessageEvent._TEMP_SRC_MAP[temp_src]  # type: ignore

        self.sender = MessageEvent.Sender(
            rawEvent=rawEvent,
            isGroup=self.is_group(),
            isGroupAnonym=self.is_group_anonym(),
        )

        self.group_id = None
        if self.is_group():
            self.group_id = rawEvent["group_id"]

    def _format_to_str(self, content: list | str) -> str:
        """对外部零信任，强制转换为 cq 字符串格式"""
        if not isinstance(content, str):
            return to_cq_str(content)
        else:
            return content

    def _format_to_array(self, content: list | str) -> list[MsgSegment]:
        """对外部零信任，强制转换为消息段格式"""
        if not isinstance(content, str):
            for item in content:
                if item["type"] == "text":
                    continue
                for k, v in item["data"].items():
                    if not isinstance(v, str):
                        continue
                    if v.isdigit() or (len(v) >= 2 and v[0] == "-" and v[1:].isdigit()):
                        item["data"][k] = int(v)
                        continue
                    try:
                        item["data"][k] = float(v)
                    except Exception:
                        pass
            return content
        else:
            return to_cq_arr(content)

    def _get_text(self, content: list[MsgSegment]) -> str:
        """获取消息中所有文本消息，返回合并字符串"""
        text_list: list[str] = []
        for item in content:
            if item["type"] == "text":
                text_list.append(item["data"]["text"])  # type: ignore
        return "".join(text_list)

    def get_segments(self, type: str) -> list[MsgSegment]:
        """提取指定类型的，消息段对象组成的消息段对象列表

        :param type: 消息段类型（对应 OneBot 标准中每种消息段对象的 type）
        :return: 消息段对象列表
        """
        return _get_cq(self.content, type)

    def get_datas(
        self, type: str, data: str, convert: Optional[Callable[[Any], Any]] = None
    ) -> list[Any]:
        """提取指定类型的消息段对象中的指定数据

        当没有任何对应类型的消息段时，为空列表。如果有对应类型的消息段，但是指定的数据键名不存在，
        则在列表中产生 :obj:`None` 值.

        可以指定 `convert` 来强制转换类型，不填则不使用类型转换

        使用示例如下：

        .. code:: python

           # 假设 event 是 MessageEvent 对象，即象征一个消息事件
           datas = event.get_datas('at', 'qq')
           # datas 将是此事件中，所有 at 消息段的 "qq" 数据值所组成的列表

        :param type: 消息段类型（对应 OneBot 标准中每种消息段对象的 type）
        :param data: 消息段对象 `data` 中的键名
        :param convert: 类型转换使用的函数
        :return: 值列表
        """
        return _get_cq_params(self.content, type, data, convert)

    def is_private(self) -> bool:
        """是否为私聊消息（注意群临时会话属于该类别）"""
        return self.raw["message_type"] == "private"

    def is_friend(self) -> bool:
        """是否为好友消息"""
        return (
            self.raw["message_type"] == "private" and self.raw["sub_type"] == "friend"
        )

    def is_group(self) -> bool:
        """是否为群消息（正常群消息、群匿名消息、群自身消息、群系统消息属于该类型）"""
        return self.raw["message_type"] == "group"

    def is_group_normal(self) -> bool:
        """是否为正常群消息"""
        return self.raw["message_type"] == "group" and self.raw["sub_type"] == "normal"

    def is_group_anonym(self) -> bool:
        """是否为匿名群消息"""
        return (
            self.raw["message_type"] == "group" and self.raw["sub_type"] == "anonymous"
        )

    def is_group_self(self) -> bool:
        """是否为群自身消息（即 bot 自己群中发的消息）"""
        return (
            self.raw["message_type"] == "group" and self.raw["sub_type"] == "group_self"
        )

    def is_group_temp(self) -> bool:
        """是否为群临时会话（属于私聊的一种）"""
        return self.raw["message_type"] == "private" and self.raw["sub_type"] == "group"

    def is_temp(self) -> bool:
        """是否为临时会话（属于私聊的一种）"""
        return "temp_source" in self.raw.keys()

    def is_group_notice(self) -> bool:
        """是否为群中的\"系统消息\" """
        return self.raw["message_type"] == "group" and self.raw["sub_type"] == "notice"

    _TEMP_SRC_MAP = {
        0: "群聊",
        1: "QQ咨询",
        2: "查找",
        3: "QQ电影",
        4: "热聊",
        6: "验证消息",
        7: "多人聊天",
        8: "约会",
        9: "通讯录",
    }

    class Sender:
        """消息事件发送者数据结构

        .. admonition:: 提示
           :class: tip

           一般无需手动实例化该类，多数情况会直接使用本类对象，或将本类用作类型注解。
        """

        def __init__(self, rawEvent: dict, isGroup: bool, isGroupAnonym: bool) -> None:
            self._rawEvent = rawEvent
            self._isGroup = isGroup
            self._isGroupAnonym = isGroupAnonym

            #: 发送者的 qq 号
            self.id: int
            #: 发送者昵称
            self.nickname: Optional[str]
            #: 发送者性别
            self.sex: Optional[str]
            #: 发送者年龄
            self.age: Optional[int]
            #: 发送者的群名片
            self.group_card: Optional[str]
            #: 发送者的群中角色
            self.group_role: Optional[Literal["owner", "admin", "member", "anonymous"]]
            #: 发送者的群头衔
            self.group_title: Optional[str]
            #: 发送者的地区
            self.group_area: Optional[str]
            #: 发送者的群等级
            self.group_level: Optional[str]

            #: 匿名发送者的 id（此属性只在事件为群匿名消息事件时存在）
            self.anonym_id: Optional[int]
            #: 匿名发送者的名字（此属性只在事件为群匿名消息事件时存在）
            self.anonym_name: Optional[str]
            #: 匿名发送者的匿名 flag（此属性只在事件为群匿名消息事件时存在）
            self.anonym_flag: Optional[str]

            self.id = rawEvent["user_id"]
            self.nickname = rawEvent["sender"].get("nickname", None)
            self.sex = rawEvent["sender"].get("sex", None)
            self.age = rawEvent["sender"].get("age", None)

            self.group_card = rawEvent["sender"].get("card", None)
            self.group_role = rawEvent["sender"].get("role", None)
            self.group_title = rawEvent["sender"].get("title", None)
            self.group_area = rawEvent["sender"].get("area", None)
            self.group_level = rawEvent["sender"].get("level", None)

            if isGroup and isGroupAnonym:
                self.anonym_id = rawEvent["anonymous"].get("id", None)
                self.anonym_name = rawEvent["anonymous"].get("name", None)
                self.anonym_flag = rawEvent["anonymous"].get("flag", None)

        def is_group_owner(self) -> bool:
            """判断是否为群主，若不是或不是群类型消息，返回 False"""
            if not self._isGroup:
                return False
            return self.group_role == "owner"

        def is_group_admin(self) -> bool:
            """判断是否为群管理（包含群主），若不是或不是群类型消息，返回 False"""
            if not self._isGroup:
                return False
            return self.group_role == "admin" or self.group_role == "owner"

        def only_group_member(self) -> bool:
            """判断是否只是群员（注意只是群员，不包括群主、管理和匿名），若不是或不是群类型消息，返回 False"""
            if not self._isGroup:
                return False
            return self.group_role == "member"

        def is_bot(self) -> bool:
            """判断消息是否是bot自己发送的"""
            return self.id == self._rawEvent["self_id"]


class RequestEvent(BotEvent):
    """请求事件类型，对应两种可能：加好友请求和加群请求

    .. admonition:: 提示
       :class: tip

       一般无需手动实例化该类，多数情况会直接使用本类对象，或将本类用作类型注解。
    """

    def __init__(self, rawEvent: dict) -> None:
        super().__init__(rawEvent)

        #: 收到事件的机器人 qq 号
        self.bot_id: int = rawEvent.get("self_id")  # type: ignore
        #: 事件的来源 qq 号
        self.from_id: int
        #: 事件的来源群号，请求来源于私聊时此属性为 :obj:`None`
        self.from_group_id: Optional[int]
        #: 加群或加好友的验证消息
        self.req_comment: str
        #: 加群或加好友请求的 flag，调用相关 API 时，需要使用
        self.req_flag: str
        #: 加群请求类型：直接加入和邀请，请求来源于私聊时此属性为 :obj:`None`
        self.group_req_type: Optional[Literal["add", "invite"]]

        self._init()

    @property
    def time(self) -> int:
        """事件发生时刻的时间戳"""
        return self.raw.get("time")  # type: ignore

    @property
    def type(self) -> Literal["request"]:
        """事件的类型（返回指定字面量）"""
        return "request"

    def _init(self) -> None:
        rawEvent = self.raw
        self.group_req_type = None
        self.from_group_id = None

        if self.is_friend_req():
            self.from_id = rawEvent["user_id"]
            self.req_comment = rawEvent["comment"]
            self.req_flag = rawEvent["flag"]
        elif self.is_group_req():
            self.group_req_type = rawEvent["sub_type"]
            self.from_id = rawEvent["user_id"]
            self.from_group_id = rawEvent["group_id"]
            self.req_comment = rawEvent["comment"]
            self.req_flag = rawEvent["flag"]

    def is_friend_req(self) -> bool:
        """是否为加好友请求"""
        return self.raw["request_type"] == "friend"

    def is_group_req(self) -> bool:
        """是否为加群请求"""
        return self.raw["request_type"] == "group"


class NoticeEvent(BotEvent):
    """通知事件类型

    .. admonition:: 提示
       :class: tip

       一般无需手动实例化该类，多数情况会直接使用本类对象，或将本类用作类型注解。

    .. admonition:: 注意
       :class: caution

       受 onebot 协议实现项目的影响，及对通知事件本身复杂性的考虑，通知事件大多数实例属性，
       只会在特定类别的通知事件中存在。各个属性的含义与存在的时机，已在下方的注释说明。

       如果你仍不确定某个属性在何时出现，建议直接调试查看存在的属性。例如通过
       `print(event.__dict__)` 或调试器查看。
    """

    def __init__(self, rawEvent: dict) -> None:
        super().__init__(rawEvent)
        #: 收到事件的机器人 qq 号
        self.bot_id: int = rawEvent.get("self_id")  # type: ignore
        # 修复某些 onebot 协议实现，user_id 缺失的问题
        if "target_id" in rawEvent.keys() and "user_id" not in rawEvent:
            rawEvent["user_id"] = rawEvent["target_id"]

        #: 通知作用者或主体方的 id，如被禁言的一方
        self.user_id: int
        #: 通知若发生在群中的群 id
        self.group_id: int
        #: 通知发起者或操作方的 id，如禁言别人的管理员
        self.operator_id: int
        #: 通知涉及消息时的消息 id
        self.msg_id: int
        #: 入群通知事件的入群类型：管理员同意或管理员邀请
        self.join_group_type: Literal["approve", "invite"]
        #: 退群通知事件的退群类型：自退群、踢出、bot 账号被踢
        self.leave_group_type: Literal["leave", "kick", "kick_me"]
        #: 群管理员变动通知事件类型：设置管理员或取消管理员
        self.admin_change_type: Literal["set", "unset"]
        #: 文件上传通知事件的文件信息数据结构
        self.file: NoticeEvent.File
        #: 群禁言通知事件的类型：禁言、解除禁言
        self.group_ban_type: Literal["ban", "lift_ban"]
        #: 群禁言通知事件的禁言时长
        self.ban_time: int
        #: 群荣誉变更通知事件的荣誉类型：龙王、群聊之火、快乐源泉
        self.honor_change_type: Literal["talkactive", "performer", "emotion"]
        #: 群头衔变更通知事件的新头衔
        self.new_title: str
        #: 群名片更新通知事件的旧名片，名片为空时对应属性为空字符串
        self.old_card: str
        #: 群名片更新通知事件的新名片，名片为空时对应属性为空字符串
        self.new_card: str
        #: 客户端在线状态变更的通知事件的，客户端信息数据结构
        self.client: NoticeEvent.Client
        #: 精华消息变更通知事件的类型：添加或删除
        self.essence_change_type: Literal["add", "delete"]

        self._init()

    @property
    def time(self) -> int:
        return self.raw.get("time")  # type: ignore

    @property
    def type(self) -> Literal["notice"]:
        return "notice"

    def _init(self) -> None:
        """外部确认为该类型事件时，调用此方法。"""
        rawEvent = self.raw

        if self.is_friend_recall():
            self.user_id = rawEvent["user_id"]
            self.msg_id = rawEvent["message_id"]
        elif self.is_group_recall():
            self.user_id = rawEvent["user_id"]
            self.group_id = rawEvent["group_id"]
            self.operator_id = rawEvent["operator_id"]
            self.msg_id = rawEvent["message_id"]
        elif self.is_group_increase():
            self.join_group_type = rawEvent["sub_type"]
            self.user_id = rawEvent["user_id"]
            self.group_id = rawEvent["group_id"]
            self.operator_id = rawEvent["operator_id"]
        elif self.is_group_decrease():
            self.leave_group_type = rawEvent["sub_type"]
            self.user_id = rawEvent["user_id"]
            self.group_id = rawEvent["group_id"]
            self.operator_id = rawEvent["operator_id"]
        elif self.is_group_admin():
            self.admin_change_type = rawEvent["sub_type"]
            self.user_id = rawEvent["user_id"]
            self.group_id = rawEvent["group_id"]
        elif self.is_group_upload():
            self.user_id = rawEvent["user_id"]
            self.group_id = rawEvent["group_id"]
            self.file = NoticeEvent.File(rawEvent, isGroup=True)
        elif self.is_group_ban():
            self.user_id = rawEvent["user_id"]
            self.group_id = rawEvent["group_id"]
            self.operator_id = rawEvent["operator_id"]
            self.group_ban_type = rawEvent["sub_type"]
            self.ban_time = rawEvent["duration"]
        elif self.is_friend_add():
            self.user_id = rawEvent["user_id"]
        elif self.is_poke():
            self.user_id = rawEvent["target_id"]
            self.operator_id = rawEvent["user_id"]
            if "group_id" in rawEvent.keys():
                self.group_id = rawEvent["group_id"]
        elif self.is_lucky_king():
            self.user_id = rawEvent["target_id"]
            self.group_id = rawEvent["group_id"]
            self.operator_id = rawEvent["user_id"]
        elif self.is_honor():
            self.honor_change_type = rawEvent["honor_type"]
            self.user_id = rawEvent["user_id"]
            self.group_id = rawEvent["group_id"]
        elif self.is_title():
            self.new_title = rawEvent["title"]
            self.user_id = rawEvent["user_id"]
            self.group_id = rawEvent["group_id"]
        elif self.is_group_card():
            self.old_card = rawEvent["card_old"]
            self.new_card = rawEvent["card_new"]
            self.user_id = rawEvent["user_id"]
            self.group_id = rawEvent["group_id"]
        elif self.is_offline_file():
            self.user_id = rawEvent["user_id"]
            self.file = NoticeEvent.File(rawEvent, isGroup=False)
        elif self.is_client_status():
            self.client = NoticeEvent.Client(rawEvent)
        elif self.is_essence():
            self.essence_change_type = rawEvent["sub_type"]
            self.user_id = rawEvent["sender_id"]
            self.group_id = rawEvent["group_id"]
            self.operator_id = rawEvent["operator_id"]
            self.msg_id = rawEvent["message_id"]

    def is_group(self) -> bool:
        """是否是来自群的通知事件"""
        return "group_id" in self.raw.keys()

    def is_group_upload(self) -> bool:
        """是否是群文件上传通知"""
        return self.raw["notice_type"] == "group_upload"

    def is_group_admin(self) -> bool:
        """是否是群管理员变更通知"""
        return self.raw["notice_type"] == "group_admin"

    def is_group_decrease(self) -> bool:
        """是否是群成员减少通知"""
        return self.raw["notice_type"] == "group_decrease"

    def is_group_increase(self) -> bool:
        """是否是群成员增加通知"""
        return self.raw["notice_type"] == "group_increase"

    def is_group_ban(self) -> bool:
        """是否是群禁言通知"""
        return self.raw["notice_type"] == "group_ban"

    def is_friend_add(self) -> bool:
        """是否是好友添加通知"""
        return self.raw["notice_type"] == "friend_add"

    def is_group_recall(self) -> bool:
        """是否是群聊消息撤回通知"""
        return self.raw["notice_type"] == "group_recall"

    def is_friend_recall(self) -> bool:
        """是否是私聊消息撤回通知"""
        return self.raw["notice_type"] == "friend_recall"

    def is_group_card(self) -> bool:
        """是否是群名片变更通知"""
        return self.raw["notice_type"] == "group_card"

    def is_offline_file(self) -> bool:
        """是否是离线文件上传通知（即私聊文件上传）"""
        return self.raw["notice_type"] == "offline_file"

    def is_client_status(self) -> bool:
        """是否是客户端状态通知"""
        return self.raw["notice_type"] == "client_status"

    def is_essence(self) -> bool:
        """是否是精华消息变更通知"""
        return self.raw["notice_type"] == "essence"

    def is_notify(self) -> bool:
        """是否为系统通知（包含群荣誉变更、戳一戳、群红包幸运王、群成员头衔变更）"""
        return self.raw["notice_type"] == "notify"

    def is_honor(self) -> bool:
        """是否是群荣誉变更通知"""
        return self.raw["notice_type"] == "notify" and self.raw["sub_type"] == "honor"

    def is_poke(self) -> bool:
        """是否是戳一戳通知"""
        return self.raw["notice_type"] == "notify" and self.raw["sub_type"] == "poke"

    def is_lucky_king(self) -> bool:
        """是否是群红包幸运王通知"""
        return (
            self.raw["notice_type"] == "notify" and self.raw["sub_type"] == "lucky_king"
        )

    def is_title(self) -> bool:
        """是否是群成员头衔变更通知"""
        return self.raw["notice_type"] == "notify" and self.raw["sub_type"] == "title"

    class File:
        """文件上传通知的文件信息数据结构

        .. admonition:: 提示
           :class: tip

           一般无需手动实例化该类，多数情况会直接使用本类对象，或将本类用作类型注解。
        """

        def __init__(self, rawEvent: dict, isGroup: bool) -> None:
            #: 文件 id，私聊文件上传时为 :obj:`None`
            self.id: Optional[str] = None
            #: 文件名
            self.name: str
            #: 文件大小
            self.size: int
            #: 文件 busid，私聊文件上传时为 :obj:`None`
            self.busid: Optional[int] = None
            #: 文件 url 地址，群聊文件上传时为 :obj:`None`
            self.url: Optional[str] = None

            self.name = rawEvent["file"]["name"]
            self.size = rawEvent["file"]["size"]
            if isGroup:
                self.id = rawEvent["file"]["id"]
                self.busid = rawEvent["file"]["busid"]
            else:
                self.url = rawEvent["file"]["url"]

    class Client:
        """客户端在线状态变更通知的客户端信息数据结构

        .. admonition:: 提示
           :class: tip

           一般无需手动实例化该类，多数情况会直接使用本类对象，或将本类用作类型注解。
        """

        def __init__(self, rawEvent: dict) -> None:
            #: 当前客户端是否在线
            self.online: bool = rawEvent["online"]
            #: 当前客户端 id
            self.id: int = rawEvent["client"]["app_id"]
            #: 客户端设备名称
            self.name: str = rawEvent["client"]["device_name"]
            #: 客户端设备类型
            self.kind: str = rawEvent["client"]["device_kind"]


class MetaEvent(BotEvent):
    """元事件类型

    .. admonition:: 提示
       :class: tip

       一般无需手动实例化该类，多数情况会直接使用本类对象，或将本类用作类型注解。
    """

    def __init__(self, rawEvent: dict) -> None:
        super().__init__(rawEvent)
        #: 收到事件的机器人 qq 号
        self.bot_id: int = rawEvent.get("self_id")  # type: ignore

    @property
    def time(self) -> int:
        """事件发生时刻的时间戳"""
        return self.raw.get("time")  # type: ignore

    @property
    def type(self) -> Literal["meta"]:
        """事件的类型（返回指定字面量）"""
        return "meta"

    def is_lifecycle(self) -> bool:
        """是否是生命周期类型的元事件"""
        return self.raw["meta_event_type"] == "lifecycle"

    def is_heartbeat(self) -> bool:
        """是否是心跳类型的元事件"""
        return self.raw["meta_event_type"] == "heartbeat"


class ResponseEvent(BotEvent):
    """响应事件类型

    .. admonition:: 提示
       :class: tip

       一般无需手动实例化该类，多数情况会直接使用本类对象，或将本类用作类型注解。

    .. admonition:: 提示
       :class: tip

       onebot 标准中未定义“响应”为一种事件类型。但在 melobot 中，“响应”仍然被封装为一种事件类型。
    """

    def __init__(self, rawEvent: dict) -> None:
        super().__init__(rawEvent)
        self.id: Optional[str] = None
        #: 响应的状态码
        self.status: int
        #: 响应的数据
        self.data: Optional[dict] = None

        self._init()

    @property
    def time(self) -> int:
        """响应被 melobot 接收时的时间戳"""
        return int(time.time())

    @property
    def type(self) -> Literal["response"]:
        """事件的类型（返回指定字面量）"""
        return "response"

    def _init(self) -> None:
        rawEvent = self.raw
        self.status = rawEvent["retcode"]
        if "echo" in rawEvent.keys() and rawEvent["echo"]:
            self.id = rawEvent["echo"]
        if "data" in rawEvent.keys() and rawEvent["data"]:
            self.data = rawEvent["data"]

    def is_ok(self) -> bool:
        """是否为成功响应"""
        return self.raw["status"] == "ok"

    def is_processing(self) -> bool:
        """是否为被异步处理的响应，即未完成但在处理中"""
        return self.status == 202

    def is_failed(self) -> bool:
        """是否为失败响应"""
        return self.raw["status"] != "ok"
