from ..base.abc import BotChecker, BotEvent
from ..base.typing import TYPE_CHECKING, AsyncCallable, Callable, Optional, User, cast

if TYPE_CHECKING:
    from ..models.event import MessageEvent, NoticeEvent, RequestEvent


class MsgChecker(BotChecker):
    """初始化一个消息事件通用检查器"""

    def __init__(self, check_func: Callable[["MessageEvent"], bool]) -> None:
        """初始化一个消息事件通用检查器

        :param check_func: 检查方法
        """
        super().__init__()
        self.check_func = check_func

    async def check(self, event: BotEvent) -> bool:
        return self.check_func(cast("MessageEvent", event))


class MsgLvlChecker(BotChecker):
    """消息事件分级权限检查器

    主要分 主人、超级用户、白名单用户、普通用户、黑名单用户 五级
    """

    def __init__(
        self,
        level: User,
        owner: Optional[int] = None,
        super_users: Optional[list[int]] = None,
        white_users: Optional[list[int]] = None,
        black_users: Optional[list[int]] = None,
        ok_cb: Optional[AsyncCallable[[], None]] = None,
        fail_cb: Optional[AsyncCallable[[], None]] = None,
    ) -> None:
        """初始化一个消息事件分级权限检查器

        :param level: 允许的等级（>= 此等级才能通过校验）
        :param owner: 主人的 qq 号
        :param super_users: 超级用户 qq 号列表
        :param white_users: 白名单用户 qq 号列表
        :param black_users: 黑名单用户 qq 号列表
        :param ok_cb: 检查通过的回调
        :param fail_cb: 检查不通过的回调
        """
        super().__init__()
        self.ok_cb = ok_cb
        self.fail_cb = fail_cb
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

    async def check(self, event: BotEvent) -> bool:
        event = cast("MessageEvent", event)
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
    """群聊消息事件分级权限检查器

    基本功能与 :class:`MsgLvlChecker` 一致。但增加了白名单机制，
    不提供 `white_groups` 参数默认拒绝所有群聊消息事件。

    对所有私聊消息事件校验不通过。
    """

    def __init__(
        self,
        level: User,
        owner: Optional[int] = None,
        super_users: Optional[list[int]] = None,
        white_users: Optional[list[int]] = None,
        black_users: Optional[list[int]] = None,
        white_groups: Optional[list[int]] = None,
        ok_cb: Optional[AsyncCallable[[], None]] = None,
        fail_cb: Optional[AsyncCallable[[], None]] = None,
    ) -> None:
        """初始化一个群聊消息事件分级权限检查器

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

    async def check(self, event: BotEvent) -> bool:
        event = cast("MessageEvent", event)
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
    """私聊消息事件分级权限检查器

    基本功能与 :class:`MsgLvlChecker` 一致。

    对所有群聊消息事件校验不通过。
    """

    def __init__(
        self,
        level: User,
        owner: Optional[int] = None,
        super_users: Optional[list[int]] = None,
        white_users: Optional[list[int]] = None,
        black_users: Optional[list[int]] = None,
        ok_cb: Optional[AsyncCallable[[], None]] = None,
        fail_cb: Optional[AsyncCallable[[], None]] = None,
    ) -> None:
        """初始化一个私聊消息事件分级权限检查器

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

    async def check(self, event: BotEvent) -> bool:
        event = cast("MessageEvent", event)
        if not event.is_msg_event():
            return False
        if not event.is_private():
            return False

        return await super().check(event)


class MsgCheckerFactory:
    """消息事件分级权限检查器的工厂

    预先存储检查依据（各等级数据），指定检查等级后，可返回一个 :class:`MsgLvlChecker` 类的对象
    """

    def __init__(
        self,
        owner: Optional[int] = None,
        super_users: Optional[list[int]] = None,
        white_users: Optional[list[int]] = None,
        black_users: Optional[list[int]] = None,
        white_groups: Optional[list[int]] = None,
        ok_cb: Optional[AsyncCallable[[], None]] = None,
        fail_cb: Optional[AsyncCallable[[], None]] = None,
    ) -> None:
        """初始化一个消息事件分级权限检查器的工厂

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

        self.ok_cb = ok_cb
        self.fail_cb = fail_cb

    def get_base(
        self,
        level: User = User.USER,
        ok_cb: Optional[AsyncCallable[[], None]] = None,
        fail_cb: Optional[AsyncCallable[[], None]] = None,
    ) -> MsgLvlChecker:
        """根据内部依据和给定等级，生成一个 :class:`MsgLvlChecker` 对象

        :param level: 允许的等级（>= 此等级才能通过校验）
        :param ok_cb: 检查通过的回调（比实例化本类传入的参数优先级更高）
        :param fail_cb: 检查不通过的回调（比实例化本类传入的参数优先级更高）
        :return: 消息事件分级权限检查器
        """
        return MsgLvlChecker(
            level,
            self.owner,
            self.su_list,
            self.white_list,
            self.black_list,
            self.ok_cb if ok_cb is None else ok_cb,
            self.fail_cb if fail_cb is None else fail_cb,
        )

    def get_group(
        self,
        level: User = User.USER,
        ok_cb: Optional[AsyncCallable[[], None]] = None,
        fail_cb: Optional[AsyncCallable[[], None]] = None,
    ) -> GroupMsgLvlChecker:
        """根据内部依据和给定等级，生成一个 :class:`GroupMsgLvlChecker` 对象

        :param level: 允许的等级（>= 此等级才能通过校验）
        :param ok_cb: 检查通过的回调（比实例化本类传入的参数优先级更高）
        :param fail_cb: 检查不通过的回调（比实例化本类传入的参数优先级更高）
        :return: 群聊消息事件分级权限检查器
        """
        return GroupMsgLvlChecker(
            level,
            self.owner,
            self.su_list,
            self.white_list,
            self.black_list,
            self.white_group_list,
            self.ok_cb if ok_cb is None else ok_cb,
            self.fail_cb if fail_cb is None else fail_cb,
        )

    def get_private(
        self,
        level: User = User.USER,
        ok_cb: Optional[AsyncCallable[[], None]] = None,
        fail_cb: Optional[AsyncCallable[[], None]] = None,
    ) -> PrivateMsgLvlChecker:
        """根据内部依据和给定等级，生成一个 :class:`PrivateMsgLvlChecker` 对象

        :param level: 允许的等级（>= 此等级才能通过校验）
        :param ok_cb: 检查通过的回调（比实例化本类传入的参数优先级更高）
        :param fail_cb: 检查不通过的回调（比实例化本类传入的参数优先级更高）
        :return: 私聊消息事件分级权限检查器
        """
        return PrivateMsgLvlChecker(
            level,
            self.owner,
            self.su_list,
            self.white_list,
            self.black_list,
            self.ok_cb if ok_cb is None else ok_cb,
            self.fail_cb if fail_cb is None else fail_cb,
        )


class AtMsgChecker(BotChecker):
    """艾特消息事件检查器"""

    def __init__(self, qid: Optional[int] = None) -> None:
        """初始化一个艾特消息事件检查器

        :param qid: 被艾特的 qq 号。为空则接受所有艾特消息事件；不为空则只接受指定 qid 被艾特的艾特消息事件
        """
        super().__init__()
        self.qid = qid

    async def check(self, event: BotEvent) -> bool:
        event = cast("MessageEvent", event)
        if not event.is_msg_event():
            return False

        qids = event.get_datas("at", "qq")
        if self.qid is None:
            return len(qids) > 0
        else:
            return any(id == self.qid for id in qids)


class ReqChecker(BotChecker):
    """请求事件通用检查器"""

    def __init__(self, check_func: Callable[["RequestEvent"], bool]) -> None:
        """初始化一个请求事件通用检查器

        :param check_func: 检查方法
        """
        super().__init__()
        self.check_func = check_func

    async def check(self, event: BotEvent) -> bool:
        return self.check_func(cast("RequestEvent", event))


class NoticeChecker(BotChecker):
    """通知事件通用检查器"""

    def __init__(self, check_func: Callable[["NoticeEvent"], bool]) -> None:
        """初始化一个通知事件通用检查器

        :param check_func: 检查方法
        """
        super().__init__()
        self.check_func = check_func

    async def check(self, event: BotEvent) -> bool:
        return self.check_func(cast("NoticeEvent", event))
