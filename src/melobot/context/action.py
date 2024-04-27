from ..base.abc import ActionArgs, BotAction, BotEvent
from ..base.exceptions import BotSessionError, BotValueError, FuncSafeExited
from ..base.tools import get_id
from ..base.typing import Any, Literal, MsgNode, MsgSegment, Optional, cast
from ..models.msg import _to_cq_str_action, reply_msg, text_msg
from .session import SESSION_LOCAL
from .session import BotSessionManager as SessionManager

__all__ = (
    "send_custom",
    "send",
    "send_custom_forward",
    "send_forward",
    "msg_recall",
    "get_msg",
    "get_forward_msg",
    "get_image",
    "send_like",
    "group_kick",
    "group_ban",
    "group_whole_ban",
    "set_group_admin",
    "set_group_card",
    "set_group_name",
    "group_leave",
    "set_group_title",
    "set_friend_add",
    "set_group_add",
    "get_login_info",
    "get_stranger_info",
    "get_friend_list",
    "get_group_info",
    "get_group_list",
    "get_group_member_info",
    "get_group_member_list",
    "get_group_honor",
    "check_send_image",
    "check_send_record",
    "get_onebot_version",
    "get_onebot_status",
    "custom_action",
    "send_wait",
    "send_reply",
    "finish",
    "reply_finish",
)


class MsgActionArgs(ActionArgs):
    """消息 action 信息构造类"""

    def __init__(
        self,
        msgs: list[MsgSegment],
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
                "group_id": groupId,
                "message": msgs,
            }


def _process_msg(content: str | MsgSegment | list[MsgSegment]) -> list[MsgSegment]:
    """将多种可能的消息格式，统一转换为 cq 消息列表"""

    def verify_segment(obj: Any) -> bool:
        return (
            isinstance(obj, dict)
            and obj.get("type") is not None
            and isinstance(obj.get("data"), dict)
        )

    if isinstance(content, str):
        return [text_msg(content)]

    elif verify_segment(content):
        return [cast(MsgSegment, content)]

    elif (
        isinstance(content, list)
        and len(content) > 0
        and all(verify_segment(obj) for obj in content)
    ):
        return content

    else:
        raise BotValueError(
            f"发送的消息内容有误，当前值是：{content}，但需要以下格式之一：字符串、消息段对象、消息段对象的列表（不可为空）"
        )


@SessionManager._handle
def send_custom(
    content: str | MsgSegment | list[MsgSegment],
    isPrivate: bool,
    userId: Optional[int] = None,
    groupId: Optional[int] = None,
    cq_str: bool = False,
    wait: bool = False,
    auto: bool = True,
) -> BotAction:
    """发送消息（自定义发送目标）

    .. admonition:: 小技巧
       :class: note

       当启用了 `cq_str` 选项，且 `content` 参数为字符串时，
       `content` 字符串将不会被处理为消息段对象，此时字符串中的 cq 码将会直接生效，而不是被转义。

    .. admonition:: 警告
       :class: attention

       这个小技巧可以让你直接发送 CQ 码字符串。但是存在潜在的安全问题：
       如果将用户输入作为 CQ 码字符串的一部分发送出去，这将会造成“注入攻击”！
       用户可以构造包含恶意图片、语音的 CQ 码，让 bot 发送。

       任何时候启用 `cq_str` 选项，如需用到用户输入，务必校验。

    此接口合并了 onebot 标准中的私聊消息发送、群聊消息发送接口。

    响应数据在返回对象的  :attr:`.ActionHandle.resp.data` 属性，数据结构参考：
    `响应数据-2 <https://github.com/botuniverse/onebot-11/blob/master/api/public.md#响应数据-2>`_

    .. admonition:: 提示
       :class: tip

       本函数虽然是同步函数，但返回的对象 :class:`.ActionHandle` 是可等待的（可使用 await）。
       使用 await 会立即发生异步切换，这会使行为操作尽快执行。不使用时会创建异步任务，稍后执行

       如果你不太明白这些概念，建议直接对返回的对象使用 await

    :param content: 发送内容
    :param isPrivate: 是否是私聊
    :param userId: 如果是私聊，传入目标 qq 号；群聊置空即可
    :param groupId: 如果是群聊，传入群号；私聊置空即可
    :param cq_str: 是否以 cq 字符串发送（默认格式是消息段对象)
    :param wait: 是否等待这个行为完成
    :param auto: 是否自动发送
    :return: :class:`.ActionHandle` 对象
    """
    if isPrivate and userId is None:
        raise BotValueError("为私聊时，构建发送消息 action 必须提供 userId 参数")
    if not isPrivate and groupId is None:
        raise BotValueError("为群聊时，构建发送消息 action 必须提供 groupId 参数")
    action = BotAction(
        MsgActionArgs(_process_msg(content), isPrivate, userId, groupId),
        resp_id=get_id() if wait else None,
        ready=auto,
    )
    if cq_str:
        action = _to_cq_str_action(action)
    return action


@SessionManager._handle
def send(
    content: str | MsgSegment | list[MsgSegment],
    cq_str: bool = False,
    wait: bool = False,
    auto: bool = True,
) -> BotAction:
    """发送消息（在当前会话下自动定位发送目标）

    .. admonition:: 小技巧
       :class: note

       当启用了 `cq_str` 选项，且 `content` 参数为字符串时，
       `content` 字符串将不会被处理为消息段对象，此时字符串中的 cq 码将会直接生效，而不是被转义。

    .. admonition:: 警告
       :class: attention

       这个小技巧可以让你直接发送 CQ 码字符串。但是存在潜在的安全问题：
       如果将用户输入作为 CQ 码字符串的一部分发送出去，这将会造成“注入攻击”！
       用户可以构造包含恶意图片、语音的 CQ 码，让 bot 发送。

       任何时候启用 `cq_str` 选项，如需用到用户输入，务必校验。

    响应数据在返回对象的  :attr:`.ActionHandle.resp.data` 属性，数据结构参考：
    `响应数据-2 <https://github.com/botuniverse/onebot-11/blob/master/api/public.md#响应数据-2>`_

    .. admonition:: 提示
       :class: tip

       本函数虽然是同步函数，但返回的对象 :class:`.ActionHandle` 是可等待的（可使用 await）。
       使用 await 会立即发生异步切换，这会使行为操作尽快执行。不使用时会创建异步任务，稍后执行

       如果你不太明白这些概念，建议直接对返回的对象使用 await

    :param content: 发送内容（可以是文本、消息段对象、消息段对象列表）
    :param cq_str: 是否以 cq 字符串发送（默认格式是消息段对象)
    :param wait: 是否等待这个行为完成
    :param auto: 是否自动发送
    :return: :class:`.ActionHandle` 对象
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
            action = _to_cq_str_action(action)
        return action
    except LookupError:
        raise BotSessionError("当前会话上下文不存在，因此无法使用本方法")


class ForwardMsgActionArgs(ActionArgs):
    """转发消息 action 信息构造类"""

    def __init__(
        self,
        msgs: list[MsgNode],
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


@SessionManager._handle
def send_custom_forward(
    msgNodes: list[MsgNode],
    isPrivate: bool,
    userId: Optional[int] = None,
    groupId: Optional[int] = None,
    cq_str: bool = False,
    wait: bool = False,
    auto: bool = True,
) -> BotAction:
    """发送转发消息（自定义发送目标）

    .. admonition:: 小技巧
       :class: note

       当启用了 `cq_str` 选项，且 `content` 参数为字符串时，
       `content` 字符串将不会被处理为消息段对象，此时字符串中的 cq 码将会直接生效，而不是被转义。

    .. admonition:: 警告
       :class: attention

       这个小技巧可以让你直接发送 CQ 码字符串。但是存在潜在的安全问题：
       如果将用户输入作为 CQ 码字符串的一部分发送出去，这将会造成“注入攻击”！
       用户可以构造包含恶意图片、语音的 CQ 码，让 bot 发送。

       任何时候启用 `cq_str` 选项，如需用到用户输入，务必校验。

    响应数据在返回对象的  :attr:`.ActionHandle.resp.data` 属性，数据结构参考：

    .. code:: python

       {
           "message_id": xxx,  # int
           "forward_id": xxx   # str
       }

    .. admonition:: 提示
       :class: tip

       本函数虽然是同步函数，但返回的对象 :class:`.ActionHandle` 是可等待的（可使用 await）。
       使用 await 会立即发生异步切换，这会使行为操作尽快执行。不使用时会创建异步任务，稍后执行

       如果你不太明白这些概念，建议直接对返回的对象使用 await

    :param msgNodes: 消息结点列表
    :param isPrivate: 是否是私聊
    :param userId: 如果是私聊，传入目标 qq 号；群聊置空即可
    :param groupId: 如果是群聊，传入群号；私聊置空即可
    :param cq_str: 是否以 cq 字符串发送（默认格式是消息段对象)
    :param wait: 是否等待这个行为完成
    :param auto: 是否自动发送
    :return: :class:`.ActionHandle` 对象
    """
    action = BotAction(
        ForwardMsgActionArgs(msgNodes, isPrivate, userId, groupId),
        resp_id=get_id() if wait else None,
        ready=auto,
    )
    if cq_str:
        action = _to_cq_str_action(action)
    return action


@SessionManager._handle
def send_forward(
    msgNodes: list[MsgNode],
    cq_str: bool = False,
    wait: bool = False,
    auto: bool = True,
) -> BotAction:
    """发送转发消息（在当前会话下自动定位发送目标）

    .. admonition:: 小技巧
       :class: note

       当启用了 `cq_str` 选项，且 `content` 参数为字符串时，
       `content` 字符串将不会被处理为消息段对象，此时字符串中的 cq 码将会直接生效，而不是被转义。

    .. admonition:: 警告
       :class: attention

       这个小技巧可以让你直接发送 CQ 码字符串。但是存在潜在的安全问题：
       如果将用户输入作为 CQ 码字符串的一部分发送出去，这将会造成“注入攻击”！
       用户可以构造包含恶意图片、语音的 CQ 码，让 bot 发送。

       任何时候启用 `cq_str` 选项，如需用到用户输入，务必校验。

    响应数据在返回对象的  :attr:`.ActionHandle.resp.data` 属性，数据结构参考：

    .. code:: python

       {
           "message_id": xxx,  # int
           "forward_id": xxx   # str
       }

    .. admonition:: 提示
       :class: tip

       本函数虽然是同步函数，但返回的对象 :class:`.ActionHandle` 是可等待的（可使用 await）。
       使用 await 会立即发生异步切换，这会使行为操作尽快执行。不使用时会创建异步任务，稍后执行

       如果你不太明白这些概念，建议直接对返回的对象使用 await

    :param msgNodes: 消息结点列表
    :param cq_str: 是否以 cq 字符串发送（默认格式是消息段对象)
    :param wait: 是否等待这个行为完成
    :param auto: 是否自动发送
    :return: :class:`.ActionHandle` 对象
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
            action = _to_cq_str_action(action)
        return action
    except LookupError:
        raise BotSessionError("当前会话上下文不存在，因此无法使用本方法")


class MsgDelActionArgs(ActionArgs):
    """撤回消息 action 信息构造类"""

    def __init__(self, msgId: int) -> None:
        super().__init__()
        self.type = "delete_msg"
        self.params = {
            "message_id": msgId,
        }


@SessionManager._handle
def msg_recall(msgId: int, wait: bool = False, auto: bool = True) -> BotAction:
    """撤回消息

    响应数据在返回对象的  :attr:`.ActionHandle.resp.data` 属性，数据结构参考：
    `响应数据-3 <https://github.com/botuniverse/onebot-11/blob/master/api/public.md#响应数据-3>`_

    .. admonition:: 提示
       :class: tip

       本函数虽然是同步函数，但返回的对象 :class:`.ActionHandle` 是可等待的（可使用 await）。
       使用 await 会立即发生异步切换，这会使行为操作尽快执行。不使用时会创建异步任务，稍后执行

       如果你不太明白这些概念，建议直接对返回的对象使用 await

    :param msgId: 消息 id
    :param wait: 是否等待这个行为完成
    :param auto: 是否自动发送
    :return: :class:`.ActionHandle` 对象
    """
    return BotAction(
        MsgDelActionArgs(msgId), resp_id=get_id() if wait else None, ready=auto
    )


class GetMsgActionArgs(ActionArgs):
    """消息信息获取 action 信息构造类"""

    def __init__(self, msgId: int) -> None:
        super().__init__()
        self.type = "get_msg"
        self.params = {"message_id": msgId}


@SessionManager._handle
def get_msg(msgId: int, wait: bool = True, auto: bool = True) -> BotAction:
    """获取消息详细信息

    响应数据在返回对象的  :attr:`.ActionHandle.resp.data` 属性，数据结构参考：
    `响应数据-4 <https://github.com/botuniverse/onebot-11/blob/master/api/public.md#响应数据-4>`_

    .. admonition:: 提示
       :class: tip

       本函数虽然是同步函数，但返回的对象 :class:`.ActionHandle` 是可等待的（可使用 await）。
       使用 await 会立即发生异步切换，这会使行为操作尽快执行。不使用时会创建异步任务，稍后执行

       如果你不太明白这些概念，建议直接对返回的对象使用 await

    :param msgId: 消息 id
    :param wait: 是否等待这个行为完成
    :param auto: 是否自动发送
    :return: :class:`.ActionHandle` 对象
    """
    return BotAction(
        GetMsgActionArgs(msgId), resp_id=get_id() if wait else None, ready=auto
    )


class getForwardActionArgs(ActionArgs):
    """转发消息获取 action 信息构造类"""

    def __init__(self, forwardId: str) -> None:
        super().__init__()
        self.type = "get_forward_msg"
        self.params = {"id": forwardId}


@SessionManager._handle
def get_forward_msg(forwardId: str, wait: bool = True, auto: bool = True) -> BotAction:
    """获取转发消息的详细信息

    响应数据在返回对象的  :attr:`.ActionHandle.resp.data` 属性，数据结构参考：
    `响应数据-5 <https://github.com/botuniverse/onebot-11/blob/master/api/public.md#响应数据-5>`_

    .. admonition:: 提示
       :class: tip

       本函数虽然是同步函数，但返回的对象 :class:`.ActionHandle` 是可等待的（可使用 await）。
       使用 await 会立即发生异步切换，这会使行为操作尽快执行。不使用时会创建异步任务，稍后执行

       如果你不太明白这些概念，建议直接对返回的对象使用 await

    :param forwardId: 转发 id
    :param wait: 是否等待这个行为完成
    :param auto: 是否自动发送
    :return: :class:`.ActionHandle` 对象
    """
    return BotAction(
        getForwardActionArgs(forwardId), resp_id=get_id() if wait else None, ready=auto
    )


class getImageActionArgs(ActionArgs):
    """获取图片信息 action 信息构造类"""

    def __init__(self, fileName: str) -> None:
        super().__init__()
        self.type = "get_image"
        self.params = {"file": fileName}


@SessionManager._handle
def get_image(fileName: str, wait: bool = True, auto: bool = True) -> BotAction:
    """获取图片信息

    响应数据在返回对象的  :attr:`.ActionHandle.resp.data` 属性，数据结构参考：
    `响应数据-31 <https://github.com/botuniverse/onebot-11/blob/master/api/public.md#响应数据-31>`_

    .. admonition:: 提示
       :class: tip

       本函数虽然是同步函数，但返回的对象 :class:`.ActionHandle` 是可等待的（可使用 await）。
       使用 await 会立即发生异步切换，这会使行为操作尽快执行。不使用时会创建异步任务，稍后执行

       如果你不太明白这些概念，建议直接对返回的对象使用 await

    :param fileName: 图片文件名
    :param wait: 是否等待这个行为完成
    :param auto: 是否自动发送
    :return: :class:`.ActionHandle` 对象
    """
    return BotAction(
        getImageActionArgs(fileName), resp_id=get_id() if wait else None, ready=auto
    )


class SendLikeActionArgs(ActionArgs):
    """发送好友赞 action 信息构造类"""

    def __init__(self, userId: int, times: int = 1) -> None:
        super().__init__()
        self.type = "send_like"
        self.params = {"user_id": userId, "times": times}


@SessionManager._handle
def send_like(
    userId: int, times: int = 1, wait: bool = False, auto: bool = True
) -> BotAction:
    """发送好友赞

    响应数据在返回对象的  :attr:`.ActionHandle.resp.data` 属性，数据结构参考：
    `响应数据-6 <https://github.com/botuniverse/onebot-11/blob/master/api/public.md#响应数据-6>`_

    .. admonition:: 提示
       :class: tip

       本函数虽然是同步函数，但返回的对象 :class:`.ActionHandle` 是可等待的（可使用 await）。
       使用 await 会立即发生异步切换，这会使行为操作尽快执行。不使用时会创建异步任务，稍后执行

       如果你不太明白这些概念，建议直接对返回的对象使用 await

    :param userId: qq 号
    :param times: 赞的数量，默认为 1，每天最多 10
    :param wait: 是否等待这个行为完成
    :param auto: 是否自动发送
    :return: :class:`.ActionHandle` 对象
    """
    return BotAction(
        SendLikeActionArgs(userId, times),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class GroupKickActionArgs(ActionArgs):
    """群组踢人 action 信息构造类"""

    def __init__(self, groupId: int, userId: int, laterReject: bool = False) -> None:
        super().__init__()
        self.type = "set_group_kick"
        self.params = {
            "group_id": groupId,
            "user_id": userId,
            "reject_add_request": laterReject,
        }


@SessionManager._handle
def group_kick(
    groupId: int,
    userId: int,
    laterReject: bool = False,
    wait: bool = False,
    auto: bool = True,
) -> BotAction:
    """群组踢人

    响应数据在返回对象的  :attr:`.ActionHandle.resp.data` 属性，数据结构参考：
    `响应数据-7 <https://github.com/botuniverse/onebot-11/blob/master/api/public.md#响应数据-7>`_

    .. admonition:: 提示
       :class: tip

       本函数虽然是同步函数，但返回的对象 :class:`.ActionHandle` 是可等待的（可使用 await）。
       使用 await 会立即发生异步切换，这会使行为操作尽快执行。不使用时会创建异步任务，稍后执行

       如果你不太明白这些概念，建议直接对返回的对象使用 await

    :param groupId: 群号
    :param userId: 被踢的 qq 号
    :param laterReject: 是否拒绝此人再次加群
    :param wait: 是否等待这个行为完成
    :param auto: 是否自动发送
    :return: :class:`.ActionHandle` 对象
    """
    return BotAction(
        GroupKickActionArgs(groupId, userId, laterReject),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class GroupBanActionArgs(ActionArgs):
    """群组禁言 action 信息构造类"""

    def __init__(self, groupId: int, userId: int, duration: int) -> None:
        super().__init__()
        self.type = "set_group_ban"
        self.params = {
            "group_id": groupId,
            "user_id": userId,
            "duration": duration,
        }


@SessionManager._handle
def group_ban(
    groupId: int, userId: int, duration: int, wait: bool = False, auto: bool = True
) -> BotAction:
    """群组禁言

    响应数据在返回对象的  :attr:`.ActionHandle.resp.data` 属性，数据结构参考：
    `响应数据-8 <https://github.com/botuniverse/onebot-11/blob/master/api/public.md#响应数据-8>`_

    .. admonition:: 提示
       :class: tip

       本函数虽然是同步函数，但返回的对象 :class:`.ActionHandle` 是可等待的（可使用 await）。
       使用 await 会立即发生异步切换，这会使行为操作尽快执行。不使用时会创建异步任务，稍后执行

       如果你不太明白这些概念，建议直接对返回的对象使用 await

    :param groupId: 群号
    :param userId: 禁言的 qq 号
    :param duration: 禁言时长，为 0 则表示取消禁言
    :param wait: 是否等待这个行为完成
    :param auto: 是否自动发送
    :return: :class:`.ActionHandle` 对象
    """
    return BotAction(
        GroupBanActionArgs(groupId, userId, duration),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class GroupWholeBanActionArgs(ActionArgs):
    """群组全员禁言 action 信息构造类"""

    def __init__(self, groupId: int, enable: bool) -> None:
        super().__init__()
        self.type = "set_group_whole_ban"
        self.params = {"group_id": groupId, "enable": enable}


@SessionManager._handle
def group_whole_ban(
    groupId: int, enable: bool, wait: bool = False, auto: bool = True
) -> BotAction:
    """群组全员禁言

    响应数据在返回对象的  :attr:`.ActionHandle.resp.data` 属性，数据结构参考：
    `响应数据-10 <https://github.com/botuniverse/onebot-11/blob/master/api/public.md#响应数据-10>`_

    .. admonition:: 提示
       :class: tip

       本函数虽然是同步函数，但返回的对象 :class:`.ActionHandle` 是可等待的（可使用 await）。
       使用 await 会立即发生异步切换，这会使行为操作尽快执行。不使用时会创建异步任务，稍后执行

       如果你不太明白这些概念，建议直接对返回的对象使用 await

    :param groupId: 群号
    :param enable: 是则禁言，否则取消禁言
    :param wait: 是否等待这个行为完成
    :param auto: 是否自动发送
    :return: :class:`.ActionHandle` 对象
    """
    return BotAction(
        GroupWholeBanActionArgs(groupId, enable),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class SetGroupAdminActionArgs(ActionArgs):
    """设置群管理员 action 信息构造类"""

    def __init__(self, groupId: int, userId: int, enable: bool) -> None:
        super().__init__()
        self.type = "set_group_admin"
        self.params = {"group_id": groupId, "user_id": userId, "enable": enable}


@SessionManager._handle
def set_group_admin(
    groupId: int, userId: int, enable: bool, wait: bool = False, auto: bool = True
) -> BotAction:
    """设置群管理员

    响应数据在返回对象的  :attr:`.ActionHandle.resp.data` 属性，数据结构参考：
    `响应数据-11 <https://github.com/botuniverse/onebot-11/blob/master/api/public.md#响应数据-11>`_

    .. admonition:: 提示
       :class: tip

       本函数虽然是同步函数，但返回的对象 :class:`.ActionHandle` 是可等待的（可使用 await）。
       使用 await 会立即发生异步切换，这会使行为操作尽快执行。不使用时会创建异步任务，稍后执行

       如果你不太明白这些概念，建议直接对返回的对象使用 await

    :param groupId: 群号
    :param userId: 设置的 qq 号
    :param enable: 是则设置，否则取消
    :param wait: 是否等待这个行为完成
    :param auto: 是否自动发送
    :return: :class:`.ActionHandle` 对象
    """
    return BotAction(
        SetGroupAdminActionArgs(groupId, userId, enable),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class SetGroupCardActionArgs(ActionArgs):
    """设置群名片 action 信息构造类"""

    def __init__(self, groupId: int, userId: int, card: str) -> None:
        super().__init__()
        self.type = "set_group_card"
        self.params = {"group_id": groupId, "user_id": userId, "card": card}


@SessionManager._handle
def set_group_card(
    groupId: int, userId: int, card: str, wait: bool = False, auto: bool = True
) -> BotAction:
    """设置群名片

    响应数据在返回对象的  :attr:`.ActionHandle.resp.data` 属性，数据结构参考：
    `响应数据-13 <https://github.com/botuniverse/onebot-11/blob/master/api/public.md#响应数据-13>`_

    .. admonition:: 提示
       :class: tip

       本函数虽然是同步函数，但返回的对象 :class:`.ActionHandle` 是可等待的（可使用 await）。
       使用 await 会立即发生异步切换，这会使行为操作尽快执行。不使用时会创建异步任务，稍后执行

       如果你不太明白这些概念，建议直接对返回的对象使用 await

    :param groupId: 群号
    :param userId: 设置的 qq 号
    :param card: 新名片内容
    :param wait: 是否等待这个行为完成
    :param auto: 是否自动发送
    :return: :class:`.ActionHandle` 对象
    """
    return BotAction(
        SetGroupCardActionArgs(groupId, userId, card),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class SetGroupNameActionArgs(ActionArgs):
    """设置群名 action 信息构造类"""

    def __init__(self, groupId: int, name: str) -> None:
        super().__init__()
        self.type = "set_group_name"
        self.params = {"group_id": groupId, "group_name": name}


@SessionManager._handle
def set_group_name(
    groupId: int, name: str, wait: bool = False, auto: bool = True
) -> BotAction:
    """设置群名

    响应数据在返回对象的  :attr:`.ActionHandle.resp.data` 属性，数据结构参考：
    `响应数据-14 <https://github.com/botuniverse/onebot-11/blob/master/api/public.md#响应数据-14>`_

    .. admonition:: 提示
       :class: tip

       本函数虽然是同步函数，但返回的对象 :class:`.ActionHandle` 是可等待的（可使用 await）。
       使用 await 会立即发生异步切换，这会使行为操作尽快执行。不使用时会创建异步任务，稍后执行

       如果你不太明白这些概念，建议直接对返回的对象使用 await

    :param groupId: 群号
    :param name: 新群名
    :param wait: 是否等待这个行为完成
    :param auto: 是否自动发送
    :return: :class:`.ActionHandle` 对象
    """
    return BotAction(
        SetGroupNameActionArgs(groupId, name),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class GroupLeaveActionArgs(ActionArgs):
    """退出群组 action 信息构造类"""

    def __init__(self, groupId: int, isDismiss: bool) -> None:
        super().__init__()
        self.type = "set_group_leave"
        self.params = {"group_id": groupId, "is_dismiss": isDismiss}


@SessionManager._handle
def group_leave(
    groupId: int, isDismiss: bool, wait: bool = False, auto: bool = True
) -> BotAction:
    """退出群

    响应数据在返回对象的  :attr:`.ActionHandle.resp.data` 属性，数据结构参考：
    `响应数据-15 <https://github.com/botuniverse/onebot-11/blob/master/api/public.md#响应数据-15>`_

    .. admonition:: 提示
       :class: tip

       本函数虽然是同步函数，但返回的对象 :class:`.ActionHandle` 是可等待的（可使用 await）。
       使用 await 会立即发生异步切换，这会使行为操作尽快执行。不使用时会创建异步任务，稍后执行

       如果你不太明白这些概念，建议直接对返回的对象使用 await

    :param groupId: 群号
    :param isDismiss: 是否解散群（仅在 bot 为群主时可用）
    :param wait: 是否等待这个行为完成
    :param auto: 是否自动发送
    :return: :class:`.ActionHandle` 对象
    """
    return BotAction(
        GroupLeaveActionArgs(groupId, isDismiss),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class SetGroupTitleActionArgs(ActionArgs):
    """设置群特殊头衔 action 信息构造类"""

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


@SessionManager._handle
def set_group_title(
    groupId: int,
    userId: int,
    title: str,
    duration: int = -1,
    wait: bool = False,
    auto: bool = True,
) -> BotAction:
    """设置群特殊头衔

    响应数据在返回对象的  :attr:`.ActionHandle.resp.data` 属性，数据结构参考：
    `响应数据-16 <https://github.com/botuniverse/onebot-11/blob/master/api/public.md#响应数据-16>`_

    .. admonition:: 提示
       :class: tip

       本函数虽然是同步函数，但返回的对象 :class:`.ActionHandle` 是可等待的（可使用 await）。
       使用 await 会立即发生异步切换，这会使行为操作尽快执行。不使用时会创建异步任务，稍后执行

       如果你不太明白这些概念，建议直接对返回的对象使用 await

    :param groupId: 群号
    :param userId: 设置的 qq 号
    :param title: 头衔名
    :param duration: 生效时间，为 -1 则为无限期
    :param wait: 是否等待这个行为完成
    :param auto: 是否自动发送
    :return: :class:`.ActionHandle` 对象
    """
    return BotAction(
        SetGroupTitleActionArgs(groupId, userId, title, duration),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class SetFriendAddActionArgs(ActionArgs):
    def __init__(self, addFlag: str, approve: bool, remark: str) -> None:
        """处理加好友请求 action 信息构造类"""
        super().__init__()
        self.type = "set_friend_add_request"
        self.params = {"flag": addFlag, "approve": approve, "remark": remark}


@SessionManager._handle
def set_friend_add(
    addFlag: str, approve: bool, remark: str, wait: bool = False, auto: bool = True
) -> BotAction:
    """处理加好友请求

    响应数据在返回对象的  :attr:`.ActionHandle.resp.data` 属性，数据结构参考：
    `响应数据-17 <https://github.com/botuniverse/onebot-11/blob/master/api/public.md#响应数据-17>`_

    .. admonition:: 提示
       :class: tip

       本函数虽然是同步函数，但返回的对象 :class:`.ActionHandle` 是可等待的（可使用 await）。
       使用 await 会立即发生异步切换，这会使行为操作尽快执行。不使用时会创建异步任务，稍后执行

       如果你不太明白这些概念，建议直接对返回的对象使用 await

    :param addFlag: 好友添加 flag，对应 :attr:`~.RequestEvent.req_flag` 属性
    :param approve: 是否通过
    :param remark: 添加后的好友备注（仅用于通过请求后）
    :param wait: 是否等待这个行为完成
    :param auto: 是否自动发送
    :return: :class:`.ActionHandle` 对象
    """
    return BotAction(
        SetFriendAddActionArgs(addFlag, approve, remark),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class SetGroupAddActionArgs(ActionArgs):
    """处理加群请求 action 信息构造类"""

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


@SessionManager._handle
def set_group_add(
    addFlag: str,
    addType: Literal["add", "invite"],
    approve: bool,
    rejectReason: Optional[str] = None,
    wait: bool = False,
    auto: bool = True,
) -> BotAction:
    """处理加群请求（只有 bot 是群管理时有用）

    响应数据在返回对象的  :attr:`.ActionHandle.resp.data` 属性，数据结构参考：
    `响应数据-18 <https://github.com/botuniverse/onebot-11/blob/master/api/public.md#响应数据-18>`_

    .. admonition:: 提示
       :class: tip

       本函数虽然是同步函数，但返回的对象 :class:`.ActionHandle` 是可等待的（可使用 await）。
       使用 await 会立即发生异步切换，这会使行为操作尽快执行。不使用时会创建异步任务，稍后执行

       如果你不太明白这些概念，建议直接对返回的对象使用 await

    :param addFlag: 加群 flag，对应 :attr:`~.RequestEvent.req_flag` 属性
    :param addType: 加群类型，对应 :attr:`~.RequestEvent.group_req_type` 属性
    :param approve: 是否通过
    :param rejectReason: 如果不通过的原因回复
    :param wait: 是否等待这个行为完成
    :param auto: 是否自动发送
    :return: :class:`.ActionHandle` 对象
    """
    return BotAction(
        SetGroupAddActionArgs(addFlag, addType, approve, rejectReason),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class GetLoginInfoActionArgs(ActionArgs):
    """获取登录号信息 action 信息构造类"""

    def __init__(self) -> None:
        super().__init__()
        self.type = "get_login_info"
        self.params = {}


@SessionManager._handle
def get_login_info(wait: bool = True, auto: bool = True) -> BotAction:
    """获得 bot 登录号信息

    响应数据在返回对象的  :attr:`.ActionHandle.resp.data` 属性，数据结构参考：
    `响应数据-19 <https://github.com/botuniverse/onebot-11/blob/master/api/public.md#响应数据-19>`_

    .. admonition:: 提示
       :class: tip

       本函数虽然是同步函数，但返回的对象 :class:`.ActionHandle` 是可等待的（可使用 await）。
       使用 await 会立即发生异步切换，这会使行为操作尽快执行。不使用时会创建异步任务，稍后执行

       如果你不太明白这些概念，建议直接对返回的对象使用 await

    :param wait: 是否等待这个行为完成
    :param auto: 是否自动发送
    :return: :class:`.ActionHandle` 对象
    """
    return BotAction(
        GetLoginInfoActionArgs(), resp_id=get_id() if wait else None, ready=auto
    )


class GetStrangerInfoActionArgs(ActionArgs):
    """获取陌生人信息 action 信息构造类"""

    def __init__(self, userId: int, noCache: bool) -> None:
        super().__init__()
        self.type = "get_stranger_info"
        self.params = {"user_id": userId, "no_cache": noCache}


@SessionManager._handle
def get_stranger_info(
    userId: int, noCache: bool, wait: bool = True, auto: bool = True
) -> BotAction:
    """获取陌生人信息，也可以对好友使用

    响应数据在返回对象的  :attr:`.ActionHandle.resp.data` 属性，数据结构参考：
    `响应数据-20 <https://github.com/botuniverse/onebot-11/blob/master/api/public.md#响应数据-20>`_

    .. admonition:: 提示
       :class: tip

       本函数虽然是同步函数，但返回的对象 :class:`.ActionHandle` 是可等待的（可使用 await）。
       使用 await 会立即发生异步切换，这会使行为操作尽快执行。不使用时会创建异步任务，稍后执行

       如果你不太明白这些概念，建议直接对返回的对象使用 await

    :param userId: qq 号
    :param noCache: 是否不使用缓存
    :param wait: 是否等待这个行为完成
    :param auto: 是否自动发送
    :return: :class:`.ActionHandle` 对象
    """
    return BotAction(
        GetStrangerInfoActionArgs(userId, noCache),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class GetFriendlistActionArgs(ActionArgs):
    """获取好友列表 action 信息构造类"""

    def __init__(self) -> None:
        super().__init__()
        self.type = "get_friend_list"
        self.params = {}


@SessionManager._handle
def get_friend_list(wait: bool = True, auto: bool = True) -> BotAction:
    """获取好友列表

    响应数据在返回对象的  :attr:`.ActionHandle.resp.data` 属性，数据结构参考：
    `响应数据-21 <https://github.com/botuniverse/onebot-11/blob/master/api/public.md#响应数据-21>`_

    .. admonition:: 提示
       :class: tip

       本函数虽然是同步函数，但返回的对象 :class:`.ActionHandle` 是可等待的（可使用 await）。
       使用 await 会立即发生异步切换，这会使行为操作尽快执行。不使用时会创建异步任务，稍后执行

       如果你不太明白这些概念，建议直接对返回的对象使用 await

    :param wait: 是否等待这个行为完成
    :param auto: 是否自动发送
    :return: :class:`.ActionHandle` 对象
    """
    return BotAction(
        GetFriendlistActionArgs(), resp_id=get_id() if wait else None, ready=auto
    )


class GetGroupInfoActionArgs(ActionArgs):
    """获取群信息 action 信息构造类"""

    def __init__(self, groupId: int, noCache: bool) -> None:
        super().__init__()
        self.type = "get_group_info"
        self.params = {"group_id": groupId, "no_cache": noCache}


@SessionManager._handle
def get_group_info(
    groupId: int, noCache: bool, wait: bool = True, auto: bool = True
) -> BotAction:
    """获取群信息，可以是未加入的群聊

    响应数据在返回对象的  :attr:`.ActionHandle.resp.data` 属性，数据结构参考：
    `响应数据-22 <https://github.com/botuniverse/onebot-11/blob/master/api/public.md#响应数据-22>`_

    .. admonition:: 提示
       :class: tip

       本函数虽然是同步函数，但返回的对象 :class:`.ActionHandle` 是可等待的（可使用 await）。
       使用 await 会立即发生异步切换，这会使行为操作尽快执行。不使用时会创建异步任务，稍后执行

       如果你不太明白这些概念，建议直接对返回的对象使用 await

    :param groupId: 群号
    :param noCache: 是否不使用缓存
    :param wait: 是否等待这个行为完成
    :param auto: 是否自动发送
    :return: :class:`.ActionHandle` 对象
    """
    return BotAction(
        GetGroupInfoActionArgs(groupId, noCache),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class GetGrouplistActionArgs(ActionArgs):
    """获取群列表 action 信息构造类"""

    def __init__(self) -> None:
        super().__init__()
        self.type = "get_group_list"
        self.params = {}


@SessionManager._handle
def get_group_list(wait: bool = True, auto: bool = True) -> BotAction:
    """获取群列表。

    可能返回的建群时间都是 0，这是不准确的。准确的时间可以通过 :meth:`get_group_info` 获得

    响应数据在返回对象的  :attr:`.ActionHandle.resp.data` 属性，数据结构参考：
    `响应数据-23 <https://github.com/botuniverse/onebot-11/blob/master/api/public.md#响应数据-23>`_

    .. admonition:: 提示
       :class: tip

       本函数虽然是同步函数，但返回的对象 :class:`.ActionHandle` 是可等待的（可使用 await）。
       使用 await 会立即发生异步切换，这会使行为操作尽快执行。不使用时会创建异步任务，稍后执行

       如果你不太明白这些概念，建议直接对返回的对象使用 await

    :param wait: 是否等待这个行为完成
    :param auto: 是否自动发送
    :return: :class:`.ActionHandle` 对象
    """
    return BotAction(
        GetGrouplistActionArgs(), resp_id=get_id() if wait else None, ready=auto
    )


class GetGroupMemberInfoActionArgs(ActionArgs):
    """获取群成员信息 action 信息构造类"""

    def __init__(self, groupId: int, userId: int, noCache: bool) -> None:
        super().__init__()
        self.type = "get_group_member_info"
        self.params = {"group_id": groupId, "user_id": userId, "no_cache": noCache}


@SessionManager._handle
def get_group_member_info(
    groupId: int, userId: int, noCache: bool, wait: bool = True, auto: bool = True
) -> BotAction:
    """获取群成员信息

    响应数据在返回对象的  :attr:`.ActionHandle.resp.data` 属性，数据结构参考：
    `响应数据-24 <https://github.com/botuniverse/onebot-11/blob/master/api/public.md#响应数据-24>`_

    .. admonition:: 提示
       :class: tip

       本函数虽然是同步函数，但返回的对象 :class:`.ActionHandle` 是可等待的（可使用 await）。
       使用 await 会立即发生异步切换，这会使行为操作尽快执行。不使用时会创建异步任务，稍后执行

       如果你不太明白这些概念，建议直接对返回的对象使用 await

    :param groupId: 群号
    :param userId: qq 号
    :param noCache: 是否不使用缓存
    :param wait: 是否等待这个行为完成
    :param auto: 是否自动发送
    :return: :class:`.ActionHandle` 对象
    """
    return BotAction(
        GetGroupMemberInfoActionArgs(groupId, userId, noCache),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class GetGroupMemberlistActionArgs(ActionArgs):
    """获取群成员列表 action 信息构造类"""

    def __init__(self, groupId: int, noCache: bool) -> None:
        super().__init__()
        self.type = "get_group_member_list"
        self.params = {"group_id": groupId, "no_cache": noCache}


@SessionManager._handle
def get_group_member_list(
    groupId: int, noCache: bool, wait: bool = True, auto: bool = True
) -> BotAction:
    """获取群成员列表

    响应数据在返回对象的  :attr:`.ActionHandle.resp.data` 属性，数据结构参考：
    `响应数据-25 <https://github.com/botuniverse/onebot-11/blob/master/api/public.md#响应数据-25>`_

    .. admonition:: 提示
       :class: tip

       本函数虽然是同步函数，但返回的对象 :class:`.ActionHandle` 是可等待的（可使用 await）。
       使用 await 会立即发生异步切换，这会使行为操作尽快执行。不使用时会创建异步任务，稍后执行

       如果你不太明白这些概念，建议直接对返回的对象使用 await

    :param groupId: 群号
    :param noCache: 是否不使用缓存
    :param wait: 是否等待这个行为完成
    :param auto: 是否自动发送
    :return: :class:`.ActionHandle` 对象
    """
    return BotAction(
        GetGroupMemberlistActionArgs(groupId, noCache),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class GetGroupHonorActionArgs(ActionArgs):
    """获取群荣誉信息 action 信息构造类"""

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


@SessionManager._handle
def get_group_honor(
    groupId: int,
    type: Literal["talkative", "performer", "legend", "strong_newbie", "emotion", "all"],
    wait: bool = True,
    auto: bool = True,
) -> BotAction:
    """获取群荣誉信息

    详细说明参考：
    `获取群荣誉信息 <https://github.com/botuniverse/onebot-11/blob/master/api/public.md#get_group_honor_info-获取群荣誉信息>`_

    响应数据在返回对象的  :attr:`.ActionHandle.resp.data` 属性，数据结构参考：
    `响应数据-26 <https://github.com/botuniverse/onebot-11/blob/master/api/public.md#响应数据-26>`_

    .. admonition:: 提示
       :class: tip

       本函数虽然是同步函数，但返回的对象 :class:`.ActionHandle` 是可等待的（可使用 await）。
       使用 await 会立即发生异步切换，这会使行为操作尽快执行。不使用时会创建异步任务，稍后执行

       如果你不太明白这些概念，建议直接对返回的对象使用 await

    :param groupId: 群号
    :param type: 荣誉类型
    :param wait: 是否等待这个行为完成
    :param auto: 是否自动发送
    :return: :class:`.ActionHandle` 对象
    """
    return BotAction(
        GetGroupHonorActionArgs(groupId, type),
        resp_id=get_id() if wait else None,
        ready=auto,
    )


class CheckSendImageActionArgs(ActionArgs):
    """检查是否可以发送图片 action 信息构造类"""

    def __init__(self) -> None:
        super().__init__()
        self.type = "can_send_image"
        self.params = {}


@SessionManager._handle
def check_send_image(wait: bool = True, auto: bool = True) -> BotAction:
    """检查是否可以发送图片

    响应数据在返回对象的  :attr:`.ActionHandle.resp.data` 属性，数据结构参考：
    `响应数据-32 <https://github.com/botuniverse/onebot-11/blob/master/api/public.md#响应数据-32>`_

    .. admonition:: 提示
       :class: tip

       本函数虽然是同步函数，但返回的对象 :class:`.ActionHandle` 是可等待的（可使用 await）。
       使用 await 会立即发生异步切换，这会使行为操作尽快执行。不使用时会创建异步任务，稍后执行

       如果你不太明白这些概念，建议直接对返回的对象使用 await

    :param wait: 是否等待这个行为完成
    :param auto: 是否自动发送
    :return: :class:`.ActionHandle` 对象
    """
    return BotAction(
        CheckSendImageActionArgs(), resp_id=get_id() if wait else None, ready=auto
    )


class CheckSendRecordActionArgs(ActionArgs):
    """检查是否可以发送语音 action 信息构造类"""

    def __init__(self) -> None:
        super().__init__()
        self.type = "can_send_image"
        self.params = {}


@SessionManager._handle
def check_send_record(wait: bool = True, auto: bool = True) -> BotAction:
    """检查是否可以发送语音

    响应数据在返回对象的  :attr:`.ActionHandle.resp.data` 属性，数据结构参考：
    `响应数据-33 <https://github.com/botuniverse/onebot-11/blob/master/api/public.md#响应数据-33>`_

    .. admonition:: 提示
       :class: tip

       本函数虽然是同步函数，但返回的对象 :class:`.ActionHandle` 是可等待的（可使用 await）。
       使用 await 会立即发生异步切换，这会使行为操作尽快执行。不使用时会创建异步任务，稍后执行

       如果你不太明白这些概念，建议直接对返回的对象使用 await

    :param wait: 是否等待这个行为完成
    :param auto: 是否自动发送
    :return: :class:`.ActionHandle` 对象
    """
    return BotAction(
        CheckSendRecordActionArgs(), resp_id=get_id() if wait else None, ready=auto
    )


class GetCqVersionActionArgs(ActionArgs):
    """获取 onebot 实现版本 action 信息构造类"""

    def __init__(self) -> None:
        super().__init__()
        self.type = "get_version_info"
        self.params = {}


@SessionManager._handle
def get_onebot_version(wait: bool = True, auto: bool = True) -> BotAction:
    """获取 onebot 实现项目的版本

    响应数据在返回对象的  :attr:`.ActionHandle.resp.data` 属性，数据结构参考：
    `响应数据-35 <https://github.com/botuniverse/onebot-11/blob/master/api/public.md#响应数据-35>`_

    .. admonition:: 提示
       :class: tip

       本函数虽然是同步函数，但返回的对象 :class:`.ActionHandle` 是可等待的（可使用 await）。
       使用 await 会立即发生异步切换，这会使行为操作尽快执行。不使用时会创建异步任务，稍后执行

       如果你不太明白这些概念，建议直接对返回的对象使用 await

    :param wait: 是否等待这个行为完成
    :param auto: 是否自动发送
    :return: :class:`.ActionHandle` 对象
    """
    return BotAction(
        GetCqVersionActionArgs(), resp_id=get_id() if wait else None, ready=auto
    )


class GetCqStatusActionArgs(ActionArgs):
    """获取 onebot 实现的状态 action 信息构造类"""

    def __init__(self) -> None:
        super().__init__()
        self.type = "get_status"
        self.params = {}


@SessionManager._handle
def get_onebot_status(wait: bool = True, auto: bool = True) -> BotAction:
    """获取 onebot 实现项目的状态

    响应数据在返回对象的  :attr:`.ActionHandle.resp.data` 属性，数据结构参考：
    `响应数据-34 <https://github.com/botuniverse/onebot-11/blob/master/api/public.md#响应数据-34>`_

    .. admonition:: 提示
       :class: tip

       本函数虽然是同步函数，但返回的对象 :class:`.ActionHandle` 是可等待的（可使用 await）。
       使用 await 会立即发生异步切换，这会使行为操作尽快执行。不使用时会创建异步任务，稍后执行

       如果你不太明白这些概念，建议直接对返回的对象使用 await

    :param wait: 是否等待这个行为完成
    :param auto: 是否自动发送
    :return: :class:`.ActionHandle` 对象
    """
    return BotAction(
        GetCqStatusActionArgs(), resp_id=get_id() if wait else None, ready=auto
    )


@SessionManager._handle
def custom_action(
    type: str, params: dict, wait: bool = False, trigger: Optional[BotEvent] = None
) -> BotAction:
    """创建并自动提交一个自定义行为

    .. admonition:: 提示
       :class: tip

       本函数虽然是同步函数，但返回的对象 :class:`.ActionHandle` 是可等待的（可使用 await）。
       使用 await 会立即发生异步切换，这会使行为操作尽快执行。不使用时会创建异步任务，稍后执行

       如果你不太明白这些概念，建议直接对返回的对象使用 await

    :param type: 行为的类型
    :param params: 行为的附加参数
    :param wait: 是否等待这个行为完成
    :param trigger: 行为的触发事件（可选，这一般是给钩子函数检查触发事件用的）
    :return: :class:`.ActionHandle` 对象
    """
    args = ActionArgs()
    args.type, args.params = type, params
    return BotAction(args, get_id() if wait else None, trigger, ready=True)


async def send_wait(
    content: str | MsgSegment | list[MsgSegment],
    cq_str: bool = False,
    overtime: Optional[int] = None,
) -> None:
    """发送一条消息然后暂停当前会话（在当前会话下自动定位发送目标）

    会话应该是可暂停的，这意味着该会话应该拥有会话规则。

    .. admonition:: 小技巧
       :class: note

       当启用了 `cq_str` 选项，且 `content` 参数为字符串时，
       `content` 字符串将不会被处理为消息段对象，此时字符串中的 cq 码将会直接生效，而不是被转义。

    .. admonition:: 警告
       :class: attention

       这个小技巧可以让你直接发送 CQ 码字符串。但是存在潜在的安全问题：
       如果将用户输入作为 CQ 码字符串的一部分发送出去，这将会造成“注入攻击”！
       用户可以构造包含恶意图片、语音的 CQ 码，让 bot 发送。

       任何时候启用 `cq_str` 选项，如需用到用户输入，务必校验。

    :param content: 发送内容
    :param cq_str: 是否以 cq 字符串发送（默认格式是消息段对象)
    :param overtime: 会话暂停的超时时间，超时将抛出 :class:`.BotSessionTimeout` 异常
    """
    await send(content, cq_str)
    try:
        await SessionManager._hup(SESSION_LOCAL._get_var(), overtime)
    except LookupError:
        raise BotSessionError("当前会话上下文不存在，因此无法使用本方法")


async def send_reply(
    content: str | MsgSegment | list[MsgSegment],
    cq_str: bool = False,
    auto: bool = True,
) -> None:
    """发送一条回复消息（在当前会话下自动定位发送目标）

    .. admonition:: 小技巧
       :class: note

       当启用了 `cq_str` 选项，且 `content` 参数为字符串时，
       `content` 字符串将不会被处理为消息段对象，此时字符串中的 cq 码将会直接生效，而不是被转义。

    .. admonition:: 警告
       :class: attention

       这个小技巧可以让你直接发送 CQ 码字符串。但是存在潜在的安全问题：
       如果将用户输入作为 CQ 码字符串的一部分发送出去，这将会造成“注入攻击”！
       用户可以构造包含恶意图片、语音的 CQ 码，让 bot 发送。

       任何时候启用 `cq_str` 选项，如需用到用户输入，务必校验。

    :param content: 发送内容
    :param cq_str: 是否以 cq 字符串发送（默认格式是消息段对象)
    :param auto: 是否自动发送
    """
    try:
        content_arr = [reply_msg(SESSION_LOCAL.event.id)]
    except LookupError:
        raise BotSessionError("当前会话上下文不存在，因此无法使用本方法")
    content_arr.extend(_process_msg(content))
    await send(content_arr, cq_str, wait=False, auto=auto)


async def finish(
    content: str | MsgSegment | list[MsgSegment],
    cq_str: bool = False,
) -> None:
    """发送一条消息，然后直接结束当前事件处理方法（在当前会话下自动定位发送目标）

    只可在事件处理方法中使用。

    .. admonition:: 小技巧
       :class: note

       当启用了 `cq_str` 选项，且 `content` 参数为字符串时，
       `content` 字符串将不会被处理为消息段对象，此时字符串中的 cq 码将会直接生效，而不是被转义。

    .. admonition:: 警告
       :class: attention

       这个小技巧可以让你直接发送 CQ 码字符串。但是存在潜在的安全问题：
       如果将用户输入作为 CQ 码字符串的一部分发送出去，这将会造成“注入攻击”！
       用户可以构造包含恶意图片、语音的 CQ 码，让 bot 发送。

       任何时候启用 `cq_str` 选项，如需用到用户输入，务必校验。

    :param content: 发送内容
    :param cq_str: 是否以 cq 字符串发送（默认格式是消息段对象)
    """
    await send(content, cq_str)
    try:
        SessionManager._expire(SESSION_LOCAL._get_var())
    except LookupError:
        raise BotSessionError("当前会话上下文不存在，因此无法使用本方法")
    raise FuncSafeExited("改函数或方法被安全地直接结束，请无视这个异常")


async def reply_finish(
    content: str | MsgSegment | list[MsgSegment],
    cq_str: bool = False,
) -> None:
    """发送一条回复消息，然后直接结束当前事件处理方法（在当前会话下自动定位发送目标）

    只可在事件处理方法中使用。

    .. admonition:: 小技巧
       :class: note

       当启用了 `cq_str` 选项，且 `content` 参数为字符串时，
       `content` 字符串将不会被处理为消息段对象，此时字符串中的 cq 码将会直接生效，而不是被转义。

    .. admonition:: 警告
       :class: attention

       这个小技巧可以让你直接发送 CQ 码字符串。但是存在潜在的安全问题：
       如果将用户输入作为 CQ 码字符串的一部分发送出去，这将会造成“注入攻击”！
       用户可以构造包含恶意图片、语音的 CQ 码，让 bot 发送。

       任何时候启用 `cq_str` 选项，如需用到用户输入，务必校验。

    :param content: 发送内容
    :param cq_str: 是否以 cq 字符串发送（默认格式是消息段对象)
    """
    try:
        content_arr = [reply_msg(SESSION_LOCAL.event.id)]
    except LookupError:
        raise BotSessionError("当前会话上下文不存在，因此无法使用本方法")

    content_arr.extend(_process_msg(content))
    await send(content_arr, cq_str)
    try:
        SessionManager._expire(SESSION_LOCAL._get_var())
    except LookupError:
        raise BotSessionError("当前会话上下文不存在，因此无法使用本方法")
    raise FuncSafeExited("改函数或方法被安全地直接结束，请无视这个异常")
