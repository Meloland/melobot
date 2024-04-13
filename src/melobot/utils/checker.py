from ..base.abc import BotChecker
from ..base.exceptions import BotCheckerError
from ..base.typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Literal,
    Optional,
    User,
)

if TYPE_CHECKING:
    from ..models.event import MessageEvent, NoticeEvent, RequestEvent


class MsgLvlChecker(BotChecker):
    """消息分级检查器

    主要分 主人、超级用户、白名单用户、普通用户、黑名单用户 五级
    """

    def __init__(
        self,
        level: User,
        owner: Optional[int] = None,
        super_users: Optional[list[int]] = None,
        white_users: Optional[list[int]] = None,
        black_users: Optional[list[int]] = None,
        ok_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
        fail_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ) -> None:
        """初始化一个消息分级检查器

        :param level: 允许的等级（>= 此等级才能通过校验）
        :param owner: 主人的 qq 号
        :param super_users: 超级用户 qq 号列表
        :param white_users: 白名单用户 qq 号列表
        :param black_users: 黑名单用户 qq 号列表
        :param ok_cb: 检查通过的回调
        :param fail_cb: 检查不通过的回调
        """
        super().__init__(ok_cb, fail_cb)
        self.check_lvl = level

        self.owner = owner
        self.su_list = super_users if super_users is not None else []
        self.white_list = white_users if white_users is not None else []
        self.black_list = black_users if black_users is not None else []

    def _get_level(self, event: "MessageEvent") -> User:
        """获得事件对应的登记"""
        qid = event.sender.id

        if qid in self.black_list:
            return User.BLACK
        elif qid == self.owner:
            return User.OWNER
        elif qid in self.su_list:
            return User.SU
        elif qid in self.white_list:
            return User.WHITE
        else:
            return User.USER

    async def check(self, event: "MessageEvent") -> bool:  # type: ignore
        if not event.is_msg_event():
            return False
        e_level = self._get_level(event)
        status = 0 < e_level.value and e_level.value >= self.check_lvl.value
        if status and self.ok_cb is not None:
            await self.ok_cb()
        if not status and self.fail_cb is not None:
            await self.fail_cb()
        return status


class GroupMsgLvlChecker(MsgLvlChecker):
    """群聊消息分级检查器

    基本功能与 :class:`MsgLvlChecker` 一致。但增加了白名单机制，
    不提供 `white_groups` 参数默认拒绝所有群聊消息。

    对所有私聊消息校验不通过。
    """

    def __init__(
        self,
        level: User,
        owner: Optional[int] = None,
        super_users: Optional[list[int]] = None,
        white_users: Optional[list[int]] = None,
        black_users: Optional[list[int]] = None,
        white_groups: Optional[list[int]] = None,
        ok_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
        fail_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ) -> None:
        """初始化一个群聊消息分级检查器

        :param level: 允许的等级（>= 此等级才能通过校验）
        :param owner: 主人的 qq 号
        :param super_users: 超级用户 qq 号列表
        :param white_users: 白名单用户 qq 号列表
        :param black_users: 黑名单用户 qq 号列表
        :param white_groups: 白名单群号列表（不在其中的群不通过校验）
        :param ok_cb: 检查通过的回调
        :param fail_cb: 检查不通过的回调
        """
        super().__init__(
            level, owner, super_users, white_users, black_users, ok_cb, fail_cb
        )
        self.white_group_list = white_groups if white_groups is not None else []

    async def check(self, event: "MessageEvent") -> bool:  # type: ignore
        if not event.is_msg_event():
            return False
        if (
            not event.is_group()
            or len(self.white_group_list) == 0
            or (event.group_id not in self.white_group_list)
        ):
            return False
        return await super().check(event)


class PrivateMsgLvlChecker(MsgLvlChecker):
    """私聊消息分级检查器

    基本功能与 :class:`MsgLvlChecker` 一致。

    对所有群聊消息校验不通过。
    """

    def __init__(
        self,
        level: User,
        owner: Optional[int] = None,
        super_users: Optional[list[int]] = None,
        white_users: Optional[list[int]] = None,
        black_users: Optional[list[int]] = None,
        ok_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
        fail_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ) -> None:
        """初始化一个私聊消息分级检查器

        :param level: 允许的等级（>= 此等级才能通过校验）
        :param owner: 主人的 qq 号
        :param super_users: 超级用户 qq 号列表
        :param white_users: 白名单用户 qq 号列表
        :param black_users: 黑名单用户 qq 号列表
        :param ok_cb: 检查通过的回调
        :param fail_cb: 检查不通过的回调
        """
        super().__init__(
            level, owner, super_users, white_users, black_users, ok_cb, fail_cb
        )

    async def check(self, event: "MessageEvent") -> bool:  # type: ignore
        if not event.is_msg_event():
            return False
        if not event.is_private():
            return False
        return await super().check(event)


class MsgCheckerGen:
    """消息分级检查器的生成器

    预先存储检查依据（各等级数据），指定检查等级后，可返回一个 :class:`MsgLvlChecker` 类的对象
    """

    def __init__(
        self,
        owner: Optional[int] = None,
        super_users: Optional[list[int]] = None,
        white_users: Optional[list[int]] = None,
        black_users: Optional[list[int]] = None,
        white_groups: Optional[list[int]] = None,
        ok_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
        fail_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ) -> None:
        """初始化一个消息分级检查器的生成器

        :param owner: 主人的 qq 号
        :param super_users: 超级用户 qq 号列表
        :param white_users: 白名单用户 qq 号列表
        :param black_users: 黑名单用户 qq 号列表
        :param white_groups: 白名单群号列表（不在其中的群不通过校验）
        :param ok_cb: 检查通过的回调（这将自动附加到生成的检查器上）
        :param fail_cb: 检查不通过的回调（这将自动附加到生成的检查器上）
        """
        self.owner = owner
        self.su_list = super_users if super_users is not None else []
        self.white_list = white_users if white_users is not None else []
        self.black_list = black_users if black_users is not None else []
        self.white_group_list = white_groups if white_groups is not None else []

        self.united_ok_cb = ok_cb
        self.united_fail_cb = fail_cb

    def gen_base(self, level: User = User.USER) -> MsgLvlChecker:
        """根据内部依据和给定等级，生成一个 :class:`MsgLvlChecker` 对象

        :param level: 允许的等级（>= 此等级才能通过校验）
        :return: 消息分级检查器
        """
        return MsgLvlChecker(
            level,
            self.owner,
            self.su_list,
            self.white_list,
            self.black_list,
            self.united_ok_cb,
            self.united_fail_cb,
        )

    def gen_group(self, level: User = User.USER) -> GroupMsgLvlChecker:
        """根据内部依据和给定等级，生成一个 :class:`GroupMsgLvlChecker` 对象

        :param level: 允许的等级（>= 此等级才能通过校验）
        :return: 群聊消息分级检查器
        """
        return GroupMsgLvlChecker(
            level,
            self.owner,
            self.su_list,
            self.white_list,
            self.black_list,
            self.white_group_list,
            self.united_ok_cb,
            self.united_fail_cb,
        )

    def gen_private(self, level: User = User.USER) -> PrivateMsgLvlChecker:
        """根据内部依据和给定等级，生成一个 :class:`PrivateMsgLvlChecker` 对象

        :param level: 允许的等级（>= 此等级才能通过校验）
        :return: 私聊消息分级检查器
        """
        return PrivateMsgLvlChecker(
            level,
            self.owner,
            self.su_list,
            self.white_list,
            self.black_list,
            self.united_ok_cb,
            self.united_fail_cb,
        )


class AtChecker(BotChecker):
    """艾特消息检查器"""

    def __init__(self, qid: Optional[int] = None) -> None:
        """初始化一个艾特消息检查器

        :param qid: 被艾特的 qq 号。为空则接受所有艾特消息；不为空则只接受指定 qid 被艾特的艾特消息
        """
        super().__init__(None, None)
        self.qid = qid if qid is not None else None

    async def check(self, event: "MessageEvent") -> bool:  # type: ignore
        if not event.is_msg_event():
            return False
        id_list = event.get_datas("at", "qq")
        if self.qid is None:
            status = len(id_list) > 0
        else:
            for id in id_list:
                if id == self.qid:
                    status = True
                    break
            status = False
        return status


class FriendReqChecker(BotChecker):
    """好友请求检查器"""

    def __init__(self) -> None:
        """初始化一个好友请求检查器

        只有是请求类型中的好友请求才会通过检查
        """
        super().__init__(None, None)

    async def check(self, event: "RequestEvent") -> bool:  # type: ignore
        if not event.is_req_event():
            return False
        status = event.is_friend_req()
        return status


class GroupReqChecker(BotChecker):
    """加群请求检查器"""

    def __init__(self) -> None:
        """初始化一个加群请求检查器

        只有是请求类型中的加群请求才会通过检查
        """
        super().__init__(None, None)

    async def check(self, event: "RequestEvent") -> bool:  # type: ignore
        if not event.is_req_event():
            return False
        status = event.is_group_req()
        return status


class NoticeTypeChecker(BotChecker):
    """通知检查器"""

    SUB_TYPES = [
        "group_upload",
        "group_admin",
        "group_decrease",
        "group_increase",
        "group_ban",
        "friend_add",
        "group_recall",
        "friend_recall",
        "group_card",
        "offline_file",
        "client_status",
        "essence",
        "notify",
        "honor",
        "poke",
        "lucky_king",
        "title",
        "ALL",
    ]

    def __init__(
        self,
        sub_type: Literal[
            "group_upload",
            "group_admin",
            "group_decrease",
            "group_increase",
            "group_ban",
            "friend_add",
            "group_recall",
            "friend_recall",
            "group_card",
            "offline_file",
            "client_status",
            "essence",
            "notify",
            "honor",
            "poke",
            "lucky_king",
            "title",
            "ALL",
        ],
    ) -> None:
        """初始化一个通知检查器

        只有是给定类型的通知事件才会通过检查

        :param sub_type: 通知的类型
        """
        super().__init__(None, None)
        if sub_type not in NoticeTypeChecker.SUB_TYPES:
            raise BotCheckerError(f"通知事件类型校验器的子类型 {sub_type} 不合法")
        self.sub_type = sub_type

    async def check(self, event: "NoticeEvent") -> bool:  # type: ignore
        if not event.is_notice_event():
            return False
        if self.sub_type == "ALL":
            status = True
        else:
            check_method = getattr(event, f"is_{self.sub_type}")
            status = check_method()
        return status
