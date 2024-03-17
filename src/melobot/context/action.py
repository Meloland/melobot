import warnings

from ..models.cq import reply_msg, text_msg, to_cq_str_action
from ..types.abc import ActionArgs, BotAction
from ..types.exceptions import BotActionError, BotSessionError, DirectRetSignal
from ..types.tools import get_id
from ..types.typing import TYPE_CHECKING, CQMsgDict, Literal, MsgNodeDict, Optional
from .session import SESSION_LOCAL
from .session import BotSessionManager as CtxManager

if TYPE_CHECKING:
    from ..models.event import BotEvent, ResponseEvent

__all__ = [
    "send_custom_msg",
    "send",
    "send_custom_forward",
    "send_forward",
    "msg_recall",
    "get_msg",
    "get_forward_msg",
    "get_image",
    "mark_msg_read",
    "group_kick",
    "group_ban",
    "group_anonym_ban",
    "group_whole_ban",
    "set_group_admin",
    "set_group_card",
    "set_group_name",
    "group_leave",
    "set_group_title",
    "group_sign",
    "set_friend_add",
    "set_group_add",
    "get_login_info",
    "set_login_profile",
    "get_stranger_info",
    "get_friend_list",
    "get_undirect_friend",
    "delete_friend",
    "get_group_info",
    "get_group_list",
    "get_group_member_info",
    "get_group_member_list",
    "get_group_honor",
    "check_send_image",
    "check_send_record",
    "get_cq_version",
    "set_group_portrait",
    "ocr",
    "get_group_sys_msg",
    "upload_file",
    "get_group_filesys_info",
    "get_group_root_files",
    "get_group_files_byfolder",
    "create_group_folder",
    "delete_group_folder",
    "delete_group_file",
    "get_group_file_url",
    "get_cq_status",
    "get_atall_remain",
    "set_group_notice",
    "get_group_notice",
    "download_file",
    "get_online_clients",
    "get_group_msg_history",
    "set_group_essence",
    "get_group_essence_list",
    "get_model_show",
    "set_model_show",
    "delete_undirect_friend",
    "take_custom_action",
    "send_wait",
    "send_reply",
    "finish",
    "reply_finish",
]


class MsgActionArgs(ActionArgs):
    """
    消息 action 信息构造类
    """

    def __init__(
        self,
        msgs: list[CQMsgDict],
        isPrivate: bool,
        userId: Optional[int] = None,
        groupId: Optional[int] = None,
    ) -> None:
        super().__init__()
        self.type = "send_msg"
        if isPrivate:
            self.params = {
                "message_type": "private",
                "user_id": userId,
                "message": msgs,
            }
        else:
            self.params = {
                "message_type": "group",
                "user_id": userId,
                "group_id": groupId,
                "message": msgs,
            }


def _process_msg(content: str | CQMsgDict | list[CQMsgDict]) -> list[CQMsgDict]:
    """
    将多种可能的消息格式，统一转换为 cq 消息列表
    """
    if isinstance(content, str):
        _ = text_msg(content)
        if not isinstance(_, list):
            msgs = [_]
    elif isinstance(content, dict):
        msgs = [content]
    elif isinstance(content, list):
        temp = []
        for _ in content:
            if isinstance(_, list):
                temp.extend(_)
            else:
                temp.append(_)
        msgs = temp
    else:
        raise BotActionError("content 参数类型不正确，无法封装")
    return msgs


@CtxManager._activate
async def send_custom_msg(
    content: str | CQMsgDict | list[CQMsgDict],
    isPrivate: bool,
    userId: Optional[int] = None,
    groupId: Optional[int] = None,
    cq_str: bool = False,
    wait: bool = False,
    auto: bool = True,
) -> Optional["ResponseEvent"] | BotAction:
    """
    发送消息
    """
    if isPrivate and userId is None:
        raise BotActionError("为私聊时，构建 action 必须提供 userId 参数")
    if not isPrivate and groupId is None:
        raise BotActionError("为群聊时，构建 action 必须提供 groupId 参数")
    action = BotAction(
        MsgActionArgs(_process_msg(content), isPrivate, userId, groupId),
        resp_id=get_id() if wait else None,
        ready=auto,
    )
    if cq_str:
        action = to_cq_str_action(action)
    return action


@CtxManager._activate
async def send(
    content: str | CQMsgDict | list[CQMsgDict],
    cq_str: bool = False,
    wait: bool = False,
    auto: bool = True,
) -> Optional["ResponseEvent"] | BotAction:
    """
    在当前 session 上下文发送一条消息
    """
    try:
        session = SESSION_LOCAL
        action = BotAction(
            MsgActionArgs(
                _process_msg(content),
                session.event.is_private(),
                session.event.sender.id,
                session.event.group_id,
            ),
            resp_id=get_id() if wait else None,
            ready=auto,
        )
        if cq_str:
            action = to_cq_str_action(action)
        return action
    except LookupError:
        raise BotSessionError("当前作用域内 session 上下文不存在，因此无法使用本方法")


class ForwardMsgActionArgs(ActionArgs):
    """
    转发消息 action 信息构造类
    """

    def __init__(
        self,
        msgs: list[MsgNodeDict],
        isPrivate: bool,
        userId: Optional[int] = None,
        groupId: Optional[int] = None,
    ) -> None:
        super().__init__()
        if isPrivate:
            self.type = "send_private_forward_msg"
            self.params = {"user_id": userId, "messages": msgs, "auto_escape": True}
        else:
            self.type = "send_group_forward_msg"
            self.params = {"group_id": groupId, "messages": msgs, "auto_escape": True}


@CtxManager._activate
async def send_custom_forward(
    msgNodes: list[MsgNodeDict],
    isPrivate: bool,
    userId: Optional[int] = None,
    groupId: Optional[int] = None,
    cq_str: bool = False,
    wait: bool = False,
    auto: bool = True,
) -> Optional["ResponseEvent"] | BotAction:
    """
    转发消息发送
    """
    action = BotAction(
        ForwardMsgActionArgs(msgNodes, isPrivate, userId, groupId),
        resp_id=get_id() if wait else None,
        ready=auto,
    )
    if cq_str:
        action = to_cq_str_action(action)
    return action


@CtxManager._activate
async def send_forward(
    msgNodes: list[MsgNodeDict],
    cq_str: bool = False,
    wait: bool = False,
    auto: bool = True,
) -> Optional["ResponseEvent"] | BotAction:
    """
    在当前 session 上下文发送转发消息
    """
    try:
        session = SESSION_LOCAL
        action = BotAction(
            ForwardMsgActionArgs(
                msgNodes,
                session.event.is_private(),
                session.event.sender.id,
                session.event.group_id,
            ),
            resp_id=get_id() if wait else None,
            ready=auto,
        )
        if cq_str:
            action = to_cq_str_action(action)
        return action
    except LookupError:
        raise BotSessionError("当前作用域内 session 上下文不存在，因此无法使用本方法")


class MsgDelActionArgs(ActionArgs):
    """
    撤回消息 action 信息构造类
    """

    def __init__(self, msgId: int) -> None:
        super().__init__()
        self.type = "delete_msg"
        self.params = {
            "message_id": msgId,
        }


@CtxManager._activate
async def msg_recall(
    msgId: int, wait: bool = False, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    撤回消息
    """
    return BotAction(
        MsgDelActionArgs(msgId), resp_id=get_id() if wait else None, ready=auto
    )


class GetMsgActionArgs(ActionArgs):
    """
    消息信息获取 action 信息构造类
    """

    def __init__(self, msgId: int) -> None:
        super().__init__()
        self.type = "get_msg"
        self.params = {"message_id": msgId}


@CtxManager._activate
async def get_msg(
    msgId: int, wait: bool = True, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    获取消息详细信息
    """
    return BotAction(
        GetMsgActionArgs(msgId), resp_id=get_id() if wait else None, ready=auto
    )


class getForwardActionArgs(ActionArgs):
    """
    转发消息获取 action 信息构造类
    """

    def __init__(self, forwardId: str) -> None:
        super().__init__()
        self.type = "get_forward_msg"
        self.params = {"message_id": forwardId}


@CtxManager._activate
async def get_forward_msg(
    forwardId: str, wait: bool = True, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    转发消息获取
    """
    return BotAction(
        getForwardActionArgs(forwardId), resp_id=get_id() if wait else None, ready=auto
    )


class getImageActionArgs(ActionArgs):
    """
    获取图片信息 action 信息构造类
    """

    def __init__(self, fileName: str) -> None:
        super().__init__()
        self.type = "get_image"
        self.params = {"file": fileName}


@CtxManager._activate
async def get_image(
    fileName: str, wait: bool = True, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    获取图片信息
    """
    return BotAction(
        getImageActionArgs(fileName), resp_id=get_id() if wait else None, ready=auto
    )


class MarkMsgReadActionArgs(ActionArgs):
    """
    标记消息已读 action 信息构造类
    """

    def __init__(self, msgId: int) -> None:
        super().__init__()
        self.type = "mark_msg_as_read"
        self.params = {"message_id": msgId}


@CtxManager._activate
async def mark_msg_read(
    msgId: int, wait: bool = False, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    标记消息已读
    """
    return BotAction(
        MarkMsgReadActionArgs(msgId), resp_id=get_id() if wait else None, ready=auto
    )


class GroupKickActionArgs(ActionArgs):
    """
    群组踢人 action 信息构造类
    """

    def __init__(self, groupId: int, userId: int, laterReject: bool = False) -> None:
        super().__init__()
        self.type = "set_group_kick"
        self.params = {
            "group_id": groupId,
            "user_id": userId,
            "reject_add_request": laterReject,
        }


@CtxManager._activate
async def group_kick(
    groupId: int,
    userId: int,
    laterReject: bool = False,
    wait: bool = False,
    auto: bool = True,
) -> Optional["ResponseEvent"] | BotAction:
    """
    群组踢人
    """
    return BotAction(
        GroupKickActionArgs(groupId, userId, laterReject),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class GroupBanActionArgs(ActionArgs):
    """
    群组禁言 action 信息构造类
    """

    def __init__(self, groupId: int, userId: int, duration: int) -> None:
        super().__init__()
        self.type = "set_group_ban"
        self.params = {
            "group_id": groupId,
            "user_id": userId,
            "duration": duration,
        }


@CtxManager._activate
async def group_ban(
    groupId: int, userId: int, duration: int, wait: bool = False, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    群组禁言。
    duration 为 0 取消禁言
    """
    return BotAction(
        GroupBanActionArgs(groupId, userId, duration),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class GroupAnonymBanActionArgs(ActionArgs):
    """
    群组匿名禁言 action 信息构造类
    """

    def __init__(self, groupId: int, anonymFlag: str, duration: int) -> None:
        super().__init__()
        self.type = "set_group_anonymous_ban"
        self.params = {
            "group_id": groupId,
            "anonymous_flag": anonymFlag,
            "duration": duration,
        }


@CtxManager._activate
async def group_anonym_ban(
    groupId: int, anonymFlag: str, duration: int, wait: bool = False, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    群组匿名禁言。
    无法取消禁言
    """
    return BotAction(
        GroupAnonymBanActionArgs(groupId, anonymFlag, duration),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class GroupWholeBanActionArgs(ActionArgs):
    """
    群组全员禁言 action 信息构造类
    """

    def __init__(self, groupId: int, enable: bool) -> None:
        super().__init__()
        self.type = "set_group_whole_ban"
        self.params = {"group_id": groupId, "enable": enable}


@CtxManager._activate
async def group_whole_ban(
    groupId: int, enable: bool, wait: bool = False, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    群组全员禁言
    """
    return BotAction(
        GroupWholeBanActionArgs(groupId, enable),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class SetGroupAdminActionArgs(ActionArgs):
    """
    设置群管理员 action 信息构造类
    """

    def __init__(self, groupId: int, userId: int, enable: bool) -> None:
        super().__init__()
        self.type = "set_group_admin"
        self.params = {"group_id": groupId, "user_id": userId, "enable": enable}


@CtxManager._activate
async def set_group_admin(
    groupId: int, userId: int, enable: bool, wait: bool = False, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    设置群管理员
    """
    return BotAction(
        SetGroupAdminActionArgs(groupId, userId, enable),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class SetGroupCardActionArgs(ActionArgs):
    """
    设置群名片 action 信息构造类
    """

    def __init__(self, groupId: int, userId: int, card: str) -> None:
        super().__init__()
        self.type = "set_group_card"
        self.params = {"group_id": groupId, "user_id": userId, "card": card}


@CtxManager._activate
async def set_group_card(
    groupId: int, userId: int, card: str, wait: bool = False, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    设置群名片
    """
    return BotAction(
        SetGroupCardActionArgs(groupId, userId, card),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class SetGroupNameActionArgs(ActionArgs):
    """
    设置群名 action 信息构造类
    """

    def __init__(self, groupId: int, name: str) -> None:
        super().__init__()
        self.type = "set_group_name"
        self.params = {"group_id": groupId, "group_name": name}


@CtxManager._activate
async def set_group_name(
    groupId: int, name: str, wait: bool = False, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    设置群名 action 信息的方法
    """
    return BotAction(
        SetGroupNameActionArgs(groupId, name),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class GroupLeaveActionArgs(ActionArgs):
    """
    退出群组 action 信息构造类
    """

    def __init__(self, groupId: int, isDismiss: bool) -> None:
        super().__init__()
        self.type = "set_group_leave"
        self.params = {"group_id": groupId, "is_dismiss": isDismiss}


@CtxManager._activate
async def group_leave(
    groupId: int, isDismiss: bool, wait: bool = False, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    退出群组
    """
    return BotAction(
        GroupLeaveActionArgs(groupId, isDismiss),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class SetGroupTitleActionArgs(ActionArgs):
    """
    设置群头衔 action 信息构造类
    """

    def __init__(
        self,
        groupId: int,
        userId: int,
        title: str,
        duration: int = -1,
    ) -> None:
        super().__init__()
        self.type = "set_group_special_title"
        self.params = {
            "group_id": groupId,
            "user_id": userId,
            "special_title": title,
            "duration": duration,
        }


@CtxManager._activate
async def set_group_title(
    groupId: int,
    userId: int,
    title: str,
    duration: int = -1,
    wait: bool = False,
    auto: bool = True,
) -> Optional["ResponseEvent"] | BotAction:
    """
    设置群头衔
    """
    return BotAction(
        SetGroupTitleActionArgs(groupId, userId, title, duration),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class GroupSignActionArgs(ActionArgs):
    """
    群打卡 action 信息构造类
    """

    def __init__(self, groupId: int) -> None:
        super().__init__()
        self.type = "send_group_sign"
        self.params = {"group_id": groupId}


@CtxManager._activate
async def group_sign(
    groupId: int, wait: bool = False, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    群打卡
    """
    return BotAction(
        GroupSignActionArgs(groupId), resp_id=get_id() if wait else None, ready=auto
    )


class SetFriendAddActionArgs(ActionArgs):
    def __init__(self, addFlag: str, approve: bool, remark: str) -> None:
        """
        处理加好友请求 action 信息构造类
        """
        super().__init__()
        self.type = "set_friend_add_request"
        self.params = {"flag": addFlag, "approve": approve, "remark": remark}


@CtxManager._activate
async def set_friend_add(
    addFlag: str, approve: bool, remark: str, wait: bool = False, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    处理加好友信息。注意 remark 目前暂未实现
    """
    return BotAction(
        SetFriendAddActionArgs(addFlag, approve, remark),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class SetGroupAddActionArgs(ActionArgs):
    """
    处理加群请求 action 信息构造类
    """

    def __init__(
        self,
        addFlag: str,
        addType: Literal["add", "invite"],
        approve: bool,
        reason: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.type = "set_group_add_request"
        self.params = {
            "flag": addFlag,
            "sub_type": addType,
            "approve": approve,
        }
        if reason:
            self.params["reason"] = reason


@CtxManager._activate
async def set_group_add(
    addFlag: str,
    addType: Literal["add", "invite"],
    approve: bool,
    rejectReason: Optional[str] = None,
    wait: bool = False,
    auto: bool = True,
) -> Optional["ResponseEvent"] | BotAction:
    """
    处理加群请求
    """
    return BotAction(
        SetGroupAddActionArgs(addFlag, addType, approve, rejectReason),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class GetLoginInfoActionArgs(ActionArgs):
    """
    获取登录号信息 action 信息构造类
    """

    def __init__(self) -> None:
        super().__init__()
        self.type = "get_login_info"
        self.params = {}


@CtxManager._activate
async def get_login_info(
    wait: bool = True, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    获得登录号信息
    """
    return BotAction(
        GetLoginInfoActionArgs(), resp_id=get_id() if wait else None, ready=auto
    )


class SetLoginProfileActionArgs(ActionArgs):
    """
    设置登录号资料 action 信息构造类
    """

    def __init__(
        self, nickname: str, company: str, email: str, college: str, personalNote: str
    ) -> None:
        super().__init__()
        self.type = "set_qq_profile"
        self.params = {
            "nickname": nickname,
            "company": company,
            "email": email,
            "college": college,
            "personal_note": personalNote,
        }


@CtxManager._activate
async def set_login_profile(
    nickname: str,
    company: str,
    email: str,
    college: str,
    personalNote: str,
    wait: bool = False,
    auto: bool = True,
) -> Optional["ResponseEvent"] | BotAction:
    """
    设置登录号资料
    """
    return BotAction(
        SetLoginProfileActionArgs(nickname, company, email, college, personalNote),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class GetStrangerInfoActionArgs(ActionArgs):
    """
    获取陌生人信息 action 信息构造类
    """

    def __init__(self, userId: int, noCache: bool) -> None:
        super().__init__()
        self.type = "get_stranger_info"
        self.params = {"user_id": userId, "no_cache": noCache}


@CtxManager._activate
async def get_stranger_info(
    userId: int, noCache: bool, wait: bool = True, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    获取陌生人信息。也可以对好友使用
    """
    return BotAction(
        GetStrangerInfoActionArgs(userId, noCache),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class GetFriendlistActionArgs(ActionArgs):
    """
    获取好友列表 action 信息构造类
    """

    def __init__(self) -> None:
        super().__init__()
        self.type = "get_friend_list"
        self.params = {}


@CtxManager._activate
async def get_friend_list(
    wait: bool = True, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    获取好友列表
    """
    return BotAction(
        GetFriendlistActionArgs(), resp_id=get_id() if wait else None, ready=auto
    )


class GetUndirectFriendActionArgs(ActionArgs):
    """
    获取单向好友列表 action 信息构造类
    """

    def __init__(self) -> None:
        super().__init__()
        self.type = "get_unidirectional_friend_list"
        self.params = {}


@CtxManager._activate
async def get_undirect_friend(
    wait: bool = True, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    获取单向好友信息列表
    """
    return BotAction(
        GetUndirectFriendActionArgs(), resp_id=get_id() if wait else None, ready=auto
    )


class DeleteFriendActionArgs(ActionArgs):
    """
    删除好友 action 信息构造类
    """

    def __init__(self, userId: int) -> None:
        super().__init__()
        self.type = "delete_friend"
        self.params = {"user_id": userId}


@CtxManager._activate
async def delete_friend(
    userId: int, wait: bool = False, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    删除好友
    """
    return BotAction(
        DeleteFriendActionArgs(userId), resp_id=get_id() if wait else None, ready=auto
    )


class GetGroupInfoActionArgs(ActionArgs):
    """
    获取群信息 action 信息构造类
    """

    def __init__(self, groupId: int, noCache: bool) -> None:
        super().__init__()
        self.type = "get_group_info"
        self.params = {"group_id": groupId, "no_cache": noCache}


@CtxManager._activate
async def get_group_info(
    groupId: int, noCache: bool, wait: bool = True, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    获取群信息。可以是未加入的群聊
    """
    return BotAction(
        GetGroupInfoActionArgs(groupId, noCache),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class GetGrouplistActionArgs(ActionArgs):
    """
    获取群列表 action 信息构造类
    """

    def __init__(self) -> None:
        super().__init__()
        self.type = "get_group_list"
        self.params = {}


@CtxManager._activate
async def get_group_list(
    wait: bool = True, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    获取群列表。注意返回建群时间都是 0，这是不准确的。准确的建群时间可以通过 `get_group_info` 获得
    """
    return BotAction(
        GetGrouplistActionArgs(), resp_id=get_id() if wait else None, ready=auto
    )


class GetGroupMemberInfoActionArgs(ActionArgs):
    """
    获取群成员信息 action 信息构造类
    """

    def __init__(self, groupId: int, userId: int, noCache: bool) -> None:
        super().__init__()
        self.type = "get_group_member_info"
        self.params = {"group_id": groupId, "user_id": userId, "no_cache": noCache}


@CtxManager._activate
async def get_group_member_info(
    groupId: int, userId: int, noCache: bool, wait: bool = True, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    获取群成员信息
    """
    return BotAction(
        GetGroupMemberInfoActionArgs(groupId, userId, noCache),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class GetGroupMemberlistActionArgs(ActionArgs):
    """
    获取群成员列表 action 信息构造类
    """

    def __init__(self, groupId: int, noCache: bool) -> None:
        super().__init__()
        self.type = "get_group_member_list"
        self.params = {"group_id": groupId, "no_cache": noCache}


@CtxManager._activate
async def get_group_member_list(
    groupId: int, noCache: bool, wait: bool = True, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    获取群成员列表
    """
    return BotAction(
        GetGroupMemberlistActionArgs(groupId, noCache),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class GetGroupHonorActionArgs(ActionArgs):
    """
    获取群荣誉信息 action 信息构造类
    """

    def __init__(
        self,
        groupId: int,
        type: Literal[
            "talkative", "performer", "legend", "strong_newbie", "emotion", "all"
        ],
    ) -> None:
        super().__init__()
        self.type = "get_group_honor_info"
        self.params = {"group_id": groupId, "type": type}


@CtxManager._activate
async def get_group_honor(
    groupId: int,
    type: Literal[
        "talkative", "performer", "legend", "strong_newbie", "emotion", "all"
    ],
    wait: bool = True,
    auto: bool = True,
) -> Optional["ResponseEvent"] | BotAction:
    """
    获取群荣誉信息
    """
    return BotAction(
        GetGroupHonorActionArgs(groupId, type),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class CheckSendImageActionArgs(ActionArgs):
    """
    检查是否可以发送图片 action 信息构造类
    """

    def __init__(self) -> None:
        super().__init__()
        self.type = "can_send_image"
        self.params = {}


@CtxManager._activate
async def check_send_image(
    wait: bool = True, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    检查是否可以发送图片
    """
    return BotAction(
        CheckSendImageActionArgs(), resp_id=get_id() if wait else None, ready=auto
    )


class CheckSendRecordActionArgs(ActionArgs):
    """
    检查是否可以发送语音 action 信息构造类
    """

    def __init__(self) -> None:
        super().__init__()
        self.type = "can_send_image"
        self.params = {}


@CtxManager._activate
async def check_send_record(
    wait: bool = True, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    检查是否可以发送语音
    """
    return BotAction(
        CheckSendRecordActionArgs(), resp_id=get_id() if wait else None, ready=auto
    )


class GetCqVersionActionArgs(ActionArgs):
    """
    获取 cq 前端实现 版本信息 action 信息构造类
    """

    def __init__(self) -> None:
        super().__init__()
        self.type = "get_version_info"
        self.params = {}


@CtxManager._activate
async def get_cq_version(
    wait: bool = True, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    获取 cq 前端实现 版本信息
    """
    return BotAction(
        GetCqVersionActionArgs(), resp_id=get_id() if wait else None, ready=auto
    )


class SetGroupPortraitActionArgs(ActionArgs):
    """
    设置群头像 action 信息构造类
    """

    def __init__(self, groupId: int, file: str, cache: Literal[0, 1] = 0) -> None:
        super().__init__()
        self.type = "set_group_portrait"
        self.params = {"group_id": groupId, "file": file, "cache": cache}


@CtxManager._activate
async def set_group_portrait(
    groupId: int,
    file: str,
    cache: Literal[0, 1] = 0,
    wait: bool = False,
    auto: bool = True,
) -> Optional["ResponseEvent"] | BotAction:
    """
    设置群头像。file 参数接受本地或网络 url 和 base64 编码。
    如本地路径为：`file:///C:/Users/Richard/Pictures/1.png`。
    特别注意：目前此 API 在登录一段时间后会因 cookie 失效而失效
    """
    return BotAction(
        SetGroupPortraitActionArgs(groupId, file, cache),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class OcrActionArgs(ActionArgs):
    """
    图片 OCR action 信息构造类
    """

    def __init__(self, image: str) -> None:
        super().__init__()
        self.type = "ocr_image"
        self.params = {"image": image}


@CtxManager._activate
async def ocr(
    image: str, wait: bool = True, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    图片 OCR。image 为图片 ID
    """
    return BotAction(
        OcrActionArgs(image), resp_id=get_id() if wait else None, ready=auto
    )


class GetGroupSysMsgActionArgs(ActionArgs):
    """
    获取群系统消息 action 信息构造类
    """

    def __init__(self) -> None:
        super().__init__()
        self.type = "get_group_system_msg"
        self.params = {}


@CtxManager._activate
async def get_group_sys_msg(
    wait: bool = True, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    获取群系统消息
    """
    return BotAction(
        GetGroupSysMsgActionArgs(), resp_id=get_id() if wait else None, ready=auto
    )


class UploadFileActionArgs(ActionArgs):
    """
    发送文件 action 信息构造类
    """

    def __init__(
        self,
        isPrivate: bool,
        file: str,
        name: str,
        userId: Optional[int] = None,
        groupId: Optional[int] = None,
        groupFolderId: Optional[str] = None,
    ) -> None:
        super().__init__()
        if isPrivate:
            self.type = "upload_private_file"
            self.params = {"user_id": userId, "file": file, "name": name}
        else:
            self.type = "upload_group_file"
            self.params = {
                "group_id": groupId,
                "file": file,
                "name": name,
                "folder": groupFolderId,
            }


@CtxManager._activate
async def upload_file(
    isPrivate: bool,
    file: str,
    sendFileName: str,
    userId: Optional[int] = None,
    groupId: Optional[int] = None,
    groupFolderId: Optional[str] = None,
    wait: bool = False,
    auto: bool = True,
) -> Optional["ResponseEvent"] | BotAction:
    """
    发送文件。只支持发送本地文件。
    若为群聊文件发送，不提供 folder id，则默认上传到群文件根目录。

    示例路径：`C:/users/15742/desktop/QQ图片20230108225606.jpg`。

    （若需要发送网络文件，先使用 `download_file()` 方法生成下载网络文件的 action，
    action 响应后文件会放于 cq 前端实现 缓存文件夹中，可直接在消息段中引用）
    """
    return BotAction(
        UploadFileActionArgs(
            isPrivate, file, sendFileName, userId, groupId, groupFolderId
        ),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class GetGroupFileSysInfoActionArgs(ActionArgs):
    """
    获取群文件系统信息 action 信息构造类
    """

    def __init__(self, groupId: int) -> None:
        super().__init__()
        self.type = "get_group_file_system_info"
        self.params = {"group_id": groupId}


@CtxManager._activate
async def get_group_filesys_info(
    groupId: int, wait: bool = True, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    获取群文件系统信息
    """
    return BotAction(
        GetGroupFileSysInfoActionArgs(groupId),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class GetGroupRootFilesActionArgs(ActionArgs):
    """
    获取群根目录文件列表 action 信息构造类
    """

    def __init__(self, groupId: int) -> None:
        super().__init__()
        self.type = "get_group_root_files"
        self.params = {"group_id": groupId}


@CtxManager._activate
async def get_group_root_files(
    groupId: int, wait: bool = True, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    获取群根目录文件列表
    """
    return BotAction(
        GetGroupRootFilesActionArgs(groupId),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class GetGroupFilesByFolderActionArgs(ActionArgs):
    """
    获取群子目录文件列表 action 信息构造类
    """

    def __init__(self, groupId: int, folderId: str) -> None:
        super().__init__()
        self.type = "get_group_files_by_folder"
        self.params = {"group_id": groupId, "folder_id": folderId}


@CtxManager._activate
async def get_group_files_byfolder(
    groupId: int, folderId: str, wait: bool = True, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    获取群子目录文件列表
    """
    return BotAction(
        GetGroupFilesByFolderActionArgs(groupId, folderId),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class CreateGroupFolderActionArgs(ActionArgs):
    """
    创建群文件夹 action 信息构造类
    """

    def __init__(self, groupId: int, folderName: str) -> None:
        super().__init__()
        self.type = "create_group_file_folder"
        self.params = {"group_id": groupId, "name": folderName, "parent_id": "/"}


@CtxManager._activate
async def create_group_folder(
    groupId: int, folderName: str, wait: bool = False, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    创建群文件夹。注意：只能在根目录创建文件夹
    """
    return BotAction(
        CreateGroupFolderActionArgs(groupId, folderName),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class DeleteGroupFolderActionArgs(ActionArgs):
    """
    删除群文件夹 action 信息构造类
    """

    def __init__(self, groupId: int, folderId: str) -> None:
        super().__init__()
        self.type = "delete_group_folder"
        self.params = {"group_id": groupId, "folder_id": folderId}


@CtxManager._activate
async def delete_group_folder(
    groupId: int, folderId: str, wait: bool = False, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    删除群文件夹。
    """
    return BotAction(
        DeleteGroupFolderActionArgs(groupId, folderId),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class DeleteGroupFileActionArgs(ActionArgs):
    """
    删除群文件 action 信息构造类
    """

    def __init__(self, groupId: int, fileId: str, fileTypeId: int) -> None:
        super().__init__()
        self.type = "delete_group_file"
        self.params = {"group_id": groupId, "file_id": fileId, "busid": fileTypeId}


@CtxManager._activate
async def delete_group_file(
    groupId: int, fileId: str, fileTypeId: int, wait: bool = False, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    删除群文件。文件相关信息通过 `get_group_root_files()` 或
    `get_group_files` 的响应获得
    """
    return BotAction(
        DeleteGroupFileActionArgs(groupId, fileId, fileTypeId),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class GetGroupFileUrlActionArgs(ActionArgs):
    """
    获取群文件资源链接 action 信息构造类
    """

    def __init__(self, groupId: int, fileId: str, fileTypeId: int) -> None:
        super().__init__()
        self.type = "get_group_file_url"
        self.params = {"group_id": groupId, "file_id": fileId, "busid": fileTypeId}


@CtxManager._activate
async def get_group_file_url(
    groupId: int, fileId: str, fileTypeId: int, wait: bool = True, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    获取群文件资源链接。文件相关信息通过 `get_group_root_files()` 或
    `get_group_files` 的响应获得
    """
    return BotAction(
        GetGroupFileUrlActionArgs(groupId, fileId, fileTypeId),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class GetCqStatusActionArgs(ActionArgs):
    """
    获取 cq 前端实现 状态 action 信息构造类
    """

    def __init__(self) -> None:
        super().__init__()
        self.type = "get_status"
        self.params = {}


@CtxManager._activate
async def get_cq_status(
    wait: bool = True, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    获取 cq 前端实现 状态
    """
    return BotAction(
        GetCqStatusActionArgs(), resp_id=get_id() if wait else None, ready=auto
    )


class GetAtAllRemainActionArgs(ActionArgs):
    """
    获取群 @全体成员 剩余次数 action 信息构造类
    """

    def __init__(self, groupId: int) -> None:
        super().__init__()
        self.type = "get_group_at_all_remain"
        self.params = {"group_id": groupId}


@CtxManager._activate
async def get_atall_remain(
    groupId: int, wait: bool = True, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    获取群 @全体成员 剩余次数
    """
    return BotAction(
        GetAtAllRemainActionArgs(groupId),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class QuickHandleActionArgs(ActionArgs):
    """
    事件快速操作 action 信息构造类
    """

    def __init__(self, contextEvent: "BotEvent", operation: dict) -> None:
        super().__init__()
        self.type = ".handle_quick_operation"
        self.params = {"context": contextEvent.raw, "operation": operation}


@CtxManager._activate
async def _quick_handle(
    contextEvent: "BotEvent", operation: dict, wait: bool = False, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    事件快速操作。

    ### 提示：外部应该避免调用此方法，此方法只应在 melobot 内部使用
    """
    warnings.warn("外部应该避免调用此方法，此方法只应在内部使用", DeprecationWarning)
    return BotAction(
        QuickHandleActionArgs(contextEvent, operation),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class SetGroupNoticeActionArgs(ActionArgs):
    """
    发送群公告 action 信息构造类
    """

    def __init__(
        self, groupId: int, content: str, imageUrl: Optional[str] = None
    ) -> None:
        super().__init__()
        self.type = "_send_group_notice"
        self.params = {
            "group_id": groupId,
            "content": content,
        }
        if imageUrl:
            self.params["image"] = imageUrl


@CtxManager._activate
async def set_group_notice(
    groupId: int,
    content: str,
    imageUrl: Optional[str] = None,
    wait: bool = False,
    auto: bool = True,
) -> Optional["ResponseEvent"] | BotAction:
    """
    发送群公告。注意 `imageUrl` 只能为本地 url，示例：`file:///C:/users/15742/desktop/123.jpg`
    """
    return BotAction(
        SetGroupNoticeActionArgs(groupId, content, imageUrl),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class GetGroupNoticeActionArgs(ActionArgs):
    """
    获取群公告 action 信息构造类
    """

    def __init__(
        self,
        groupId: int,
    ) -> None:
        super().__init__()
        self.type = "_get_group_notice"
        self.params = {
            "group_id": groupId,
        }


@CtxManager._activate
async def get_group_notice(
    groupId: int, wait: bool = True, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    获取群公告。
    群公告图片有 id，但暂时没有下载的方法
    """
    return BotAction(
        GetGroupNoticeActionArgs(groupId),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class DownloadFileActionArgs(ActionArgs):
    """
    下载文件到缓存目录 action 信息构造类
    """

    def __init__(self, fileUrl: str, useThreadNum: int, headers: list | str) -> None:
        super().__init__()
        self.type = "download_file"
        self.params = {"url": fileUrl, "thread_count": useThreadNum, "headers": headers}


@CtxManager._activate
async def download_file(
    fileUrl: str,
    useThreadNum: int,
    headers: list | str,
    wait: bool = True,
    auto: bool = True,
) -> Optional["ResponseEvent"] | BotAction:
    """
    下载文件到缓存目录。`headers` 的两种格式：
    ```
    "User-Agent=YOUR_UA[\\r\\n]Referer=https://www.baidu.com"
    ```
    或
    ```python
    [
        "User-Agent=YOUR_UA",
        "Referer=https://www.baidu.com"
    ]
    ```
    """
    return BotAction(
        DownloadFileActionArgs(fileUrl, useThreadNum, headers),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class GetOnlineClientsActionArgs(ActionArgs):
    """
    获取当前账号在线客户端列表 action 信息构造类
    """

    def __init__(self, noCache: bool) -> None:
        super().__init__()
        self.type = "get_online_clients"
        self.params = {"no_cache": noCache}


@CtxManager._activate
async def get_online_clients(
    noCache: bool, wait: bool = True, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    获取当前账号在线客户端列表
    """
    return BotAction(
        GetOnlineClientsActionArgs(noCache),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class GetGroupMsgHistoryActionArgs(ActionArgs):
    """
    获取群消息历史记录 action 信息构造类
    """

    def __init__(self, msgSeq: int, groupId: int) -> None:
        super().__init__()
        self.type = "get_group_msg_history"
        self.params = {"message_seq": msgSeq, "group_id": groupId}


@CtxManager._activate
async def get_group_msg_history(
    msgSeq: int, groupId: int, wait: bool = True, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    获取群消息历史记录
    """
    return BotAction(
        GetGroupMsgHistoryActionArgs(msgSeq, groupId),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class SetGroupEssenceActionArgs(ActionArgs):
    """
    设置精华消息 action 信息构造类
    """

    def __init__(self, msgId: int, type: Literal["add", "del"]) -> None:
        super().__init__()
        if type == "add":
            self.type = "set_essence_msg"
        else:
            self.type = "delete_essence_msg"
        self.params = {"message_id": msgId}


@CtxManager._activate
async def set_group_essence(
    msgId: int, type: Literal["add", "del"], wait: bool = False, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    设置精华消息
    """
    return BotAction(
        SetGroupEssenceActionArgs(msgId, type),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class GetGroupEssencelistActionArgs(ActionArgs):
    """
    获取精华消息列表 action 信息构造类
    """

    def __init__(self, groupId: int) -> None:
        super().__init__()
        self.type = "get_essence_msg_list"
        self.params = {"group_id": groupId}


@CtxManager._activate
async def get_group_essence_list(
    groupId: int, wait: bool = True, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    获取精华消息列表
    """
    return BotAction(
        GetGroupEssencelistActionArgs(groupId),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class GetModelShowActionArgs(ActionArgs):
    """
    获取在线机型 action 信息构造类
    """

    def __init__(self, model: str) -> None:
        super().__init__()
        self.type = "_get_model_show"
        self.params = {"model": model}


@CtxManager._activate
async def get_model_show(
    model: str, wait: bool = True, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    获取在线机型
    """
    return BotAction(
        GetModelShowActionArgs(model), resp_id=get_id() if wait else None, ready=auto
    )


class SetModelShowActionArgs(ActionArgs):
    """
    设置在线机型 action 信息构造类
    """

    def __init__(self, model: str, modelShow: str) -> None:
        super().__init__()
        self.type = "_set_model_show"
        self.params = {"model": model, "model_show": modelShow}


@CtxManager._activate
async def set_model_show(
    model: str, modelShow: str, wait: bool = False, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    设置在线机型
    """
    return BotAction(
        SetModelShowActionArgs(model, modelShow),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class DeleteUndirectFriendActionArgs(ActionArgs):
    """
    删除单向好友 action 信息构造类
    """

    def __init__(self, userId: int) -> None:
        super().__init__()
        self.type = "delete_unidirectional_friend"
        self.params = {"user_id": userId}


@CtxManager._activate
async def delete_undirect_friend(
    userId: int, wait: bool = False, auto: bool = True
) -> Optional["ResponseEvent"] | BotAction:
    """
    删除单向好友
    """
    return BotAction(
        DeleteUndirectFriendActionArgs(userId),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


@CtxManager._activate
async def take_custom_action(
    action: BotAction,
) -> Optional["ResponseEvent"]:
    """
    直接发送提供的 action
    """
    action.ready = True
    return action  # type: ignore


async def send_wait(
    content: str | CQMsgDict | list[CQMsgDict],
    cq_str: bool = False,
    overtime: Optional[int] = None,
) -> None:
    """
    回复一条消息然后挂起
    """
    await send(content, cq_str)
    await SESSION_LOCAL.hup(overtime)


async def send_reply(
    content: str | CQMsgDict | list[CQMsgDict],
    cq_str: bool = False,
    wait: bool = False,
) -> Optional["ResponseEvent"]:
    """
    发送一条回复消息
    """
    try:
        content_arr = [reply_msg(SESSION_LOCAL.event.id)]
    except LookupError:
        raise BotSessionError("当前作用域内 session 上下文不存在，因此无法使用本方法")

    if isinstance(content, str):
        content_arr.append(text_msg(content))
    elif isinstance(content, dict):
        content_arr.append(content)
    else:
        content_arr.extend(content)
    return await send(content_arr, cq_str, wait)


async def finish(
    content: str | CQMsgDict | list[CQMsgDict],
    cq_str: bool = False,
) -> None:
    """
    发送一条消息，然后直接结束当前事件处理方法
    """
    await send(content, cq_str)
    SESSION_LOCAL.destory()
    raise DirectRetSignal("事件处理方法被安全地递归 return，请无视这个异常")


async def reply_finish(
    content: str | CQMsgDict | list[CQMsgDict],
    cq_str: bool = False,
) -> Optional["ResponseEvent"]:
    """
    发送一条回复消息，然后直接结束当前事件处理方法
    """
    try:
        content_arr = [reply_msg(SESSION_LOCAL.event.id)]
    except LookupError:
        raise BotSessionError("当前作用域内 session 上下文不存在，因此无法使用本方法")

    if isinstance(content, str):
        content_arr.append(text_msg(content))
    elif isinstance(content, dict):
        content_arr.append(content)
    else:
        content_arr.extend(content)
    await send(content_arr, cq_str)
    SESSION_LOCAL.destory()
    raise DirectRetSignal("事件处理方法被安全地递归 return，请无视这个异常")
