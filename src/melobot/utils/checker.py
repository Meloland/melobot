from ..base.abc import BotChecker
from ..base.exceptions import BotCheckerError
from ..base.typing import TYPE_CHECKING, Any, Callable, Coroutine, Optional, User

if TYPE_CHECKING:
    from ..models.event import MessageEvent, NoticeEvent, RequestEvent


class MsgLvlChecker(BotChecker):
    """消息分级权限校验器，不低于预设等级的 event 才会被接受."""

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
        super().__init__(ok_cb, fail_cb)
        self.check_lvl = level

        self.owner = owner
        self.su_list = super_users if super_users is not None else []
        self.white_list = white_users if white_users is not None else []
        self.black_list = black_users if black_users is not None else []

    def _get_level(self, event: "MessageEvent") -> User:
        """获得事件对应的登记."""
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
        """消息校验."""
        e_level = self._get_level(event)
        status = 0 < e_level.value and e_level.value >= self.check_lvl.value
        if status and self.ok_cb is not None:
            await self.ok_cb()
        if not status and self.fail_cb is not None:
            await self.fail_cb()
        return status


class GroupMsgLvl(MsgLvlChecker):
    """群聊消息分级权限检查器，不低于预设等级的 event 才会被接受。 不接受非白名单群聊的消息，也不接受任何私聊消息。 特别注意：如果 white_groups
    参数为 None，不启用白名单群聊校验."""

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
        super().__init__(
            level, owner, super_users, white_users, black_users, ok_cb, fail_cb
        )
        self.white_group_list = white_groups if white_groups is not None else []

    async def check(self, event: "MessageEvent") -> bool:  # type: ignore
        if (
            not event.is_group()
            or len(self.white_group_list) == 0
            or (event.group_id not in self.white_group_list)
        ):
            return False
        return await super().check(event)


class PrivateMsgLvl(MsgLvlChecker):
    """私聊消息分级权限检查器，不低于预设等级的 event 才会被接受。不接受任何群聊消息."""

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
        super().__init__(
            level, owner, super_users, white_users, black_users, ok_cb, fail_cb
        )

    async def check(self, event: "MessageEvent") -> bool:  # type: ignore
        if not event.is_private():
            return False
        return await super().check(event)


class MsgCheckerGen:
    """消息校验器生成器。预先存储校验依据（各等级数据）， 指定校验 level 后返回一个符合 MsgLvlChecker 接口的实例对象."""

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
        self.owner = owner
        self.su_list = super_users if super_users is not None else []
        self.white_list = white_users if white_users is not None else []
        self.black_list = black_users if black_users is not None else []
        self.white_group_list = white_groups if white_groups is not None else []

        self.united_ok_cb = ok_cb
        self.united_fail_cb = fail_cb

    def gen_base(self, level: User = User.USER) -> MsgLvlChecker:
        """根据内部依据，生成一个原始消息等级校验器."""
        return MsgLvlChecker(
            level,
            self.owner,
            self.su_list,
            self.white_list,
            self.black_list,
            self.united_ok_cb,
            self.united_fail_cb,
        )

    def gen_group(self, level: User = User.USER) -> GroupMsgLvl:
        """根据内部依据，生成一个群组消息等级校验器."""
        return GroupMsgLvl(
            level,
            self.owner,
            self.su_list,
            self.white_list,
            self.black_list,
            self.white_group_list,
            self.united_ok_cb,
            self.united_fail_cb,
        )

    def gen_private(self, level: User = User.USER) -> PrivateMsgLvl:
        """根据内部依据，生成一个私聊消息等级校验器."""
        return PrivateMsgLvl(
            level,
            self.owner,
            self.su_list,
            self.white_list,
            self.black_list,
            self.united_ok_cb,
            self.united_fail_cb,
        )


class AtChecker(BotChecker):
    """At 消息校验器。 如果事件中包含指定 qid 的 at 消息，则校验结果为真."""

    def __init__(self, qid: Optional[int] = None) -> None:
        super().__init__(None, None)
        self.qid = qid if qid is not None else None

    async def check(self, event: "MessageEvent") -> bool:  # type: ignore
        """当 qid 为空时，只要有 at 消息就通过校验。 如果不为空，则必须出现指定 qid 的 at 消息."""
        id_list = event.get_cq_params("at", "qq")
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
    """朋友请求事件校验器。 如果事件是来自朋友的请求事件，则校验结果为真."""

    def __init__(self) -> None:
        super().__init__(None, None)

    async def check(self, event: "RequestEvent") -> bool:  # type: ignore
        status = event.is_friend_req()
        return status


class GroupReqChecker(BotChecker):
    """群请求事件校验器。 如果事件是来自群的请求事件，则校验结果为真."""

    def __init__(self) -> None:
        super().__init__(None, None)

    async def check(self, event: "RequestEvent") -> bool:  # type: ignore
        status = event.is_group_req()
        return status


class NoticeTypeChecker(BotChecker):
    """通知事件类型校验器。 校验是否为指定通知类型的通知事件."""

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

    def __init__(self, sub_type: str) -> None:
        super().__init__(None, None)
        if sub_type not in NoticeTypeChecker.SUB_TYPES:
            raise BotCheckerError(f"通知事件类型校验器的子类型 {sub_type} 不合法")
        self.sub_type = sub_type

    async def check(self, event: "NoticeEvent") -> bool:  # type: ignore
        if self.sub_type == "ALL":
            status = True
        else:
            check_method = getattr(event, "is_" + self.sub_type)
            status = check_method()
        return status
