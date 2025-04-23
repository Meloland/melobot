from __future__ import annotations

from enum import Enum

from typing_extensions import Iterable, Literal, Optional, cast

from melobot.typ import SyncOrAsyncCallable
from melobot.utils.check import Checker

from ..adapter.event import Event, GroupMessageEvent, MessageEvent
from ..adapter.segment import AtSegment


class LevelRole(int, Enum):
    """用户权限等级枚举"""

    OWNER = 1 << 4
    SU = 1 << 3
    WHITE = 1 << 2
    NORMAL = 1 << 1
    BLACK = 1


class GroupRole(int, Enum):
    """群权限等级枚举"""

    OWNER = 1 << 2
    ADMIN = 1 << 1
    MEMBER = 1
    NOT_IN_GROUP = 0


def get_level_role(checker: MsgChecker, event: MessageEvent) -> LevelRole:
    """获得消息事件对应的分级权限等级

    :param event: 消息事件
    :return: 分级权限等级
    """
    _this = get_level_role
    _flag = (checker.black_users, checker.owner, checker.super_users, checker.white_users)
    ret = event.flag_get(_this, _flag, raise_exc=False, default=None)
    if ret is not None:
        return cast(LevelRole, ret)

    qid = event.user_id
    if qid in _flag[0]:
        res = LevelRole.BLACK
    elif qid == _flag[1]:
        res = LevelRole.OWNER
    elif qid in _flag[2]:
        res = LevelRole.SU
    elif qid in _flag[3]:
        res = LevelRole.WHITE
    else:
        res = LevelRole.NORMAL
    event.flag_set(_this, _flag, res)
    return res


def get_group_role(event: MessageEvent) -> GroupRole:
    """获得消息事件对应的群权限等级

    :param event: 消息事件
    :return: 群权限等级
    """
    _this = get_group_role
    ret = event.flag_get(_this, _this, raise_exc=False, default=None)
    if ret is not None:
        return cast(GroupRole, ret)

    if not event.is_group():
        res = cast(GroupRole, GroupRole.NOT_IN_GROUP)
    elif event.sender.is_group_owner():
        res = GroupRole.OWNER
    elif event.sender.is_group_admin():
        res = GroupRole.ADMIN
    else:
        res = GroupRole.MEMBER
    event.flag_set(_this, _this, res)
    return res


class MsgChecker(Checker[Event]):
    """消息事件分级权限检查器

    主要分 主人、超级用户、白名单用户、普通用户、黑名单用户 五级
    """

    def __init__(
        self,
        role: LevelRole | GroupRole,
        owner: Optional[int] = None,
        super_users: Optional[Iterable[int]] = None,
        white_users: Optional[Iterable[int]] = None,
        black_users: Optional[Iterable[int]] = None,
        fail_cb: Optional[SyncOrAsyncCallable[[], None]] = None,
    ) -> None:
        """初始化一个消息事件分级权限检查器

        :param role: 允许的等级（>= 此等级才能通过校验）
        :param owner: 主人的 qq 号
        :param super_users: 超级用户 qq 号
        :param white_users: 白名单用户 qq 号
        :param black_users: 黑名单用户 qq 号
        :param fail_cb: 检查不通过的回调
        """
        super().__init__(fail_cb)
        self.check_role = role

        self.owner = owner
        self.super_users = tuple(super_users) if super_users is not None else ()
        self.white_users = tuple(white_users) if white_users is not None else ()
        self.black_users = tuple(black_users) if black_users is not None else ()
        self._hash_tag: tuple[int | None | tuple, ...] = (
            self.check_role,
            self.owner,
            self.super_users,
            self.white_users,
            self.black_users,
        )

    def _check(self, event: MessageEvent) -> bool:
        e_level: LevelRole | GroupRole
        if isinstance(self.check_role, LevelRole):
            e_level = get_level_role(self, event)
            status = LevelRole.BLACK < e_level and e_level >= self.check_role
        else:
            e_level = get_group_role(event)
            status = e_level >= self.check_role
        return status

    async def check(self, event: Event) -> bool:
        status = is_msg = False
        try:
            ret, is_msg = event.flag_get(
                self.__class__, self._hash_tag, raise_exc=False, default=(None, False)
            )
            if ret is not None:
                return cast(bool, ret)

            # 不要使用 isinstace，避免通过反射模式注入的 event 依赖产生误判结果
            if not event.is_message():
                status = is_msg = False
            else:
                is_msg = True
                status = self._check(cast(MessageEvent, event))

            event.flag_set(self.__class__, self._hash_tag, (status, is_msg))
            return status

        finally:
            if not status and is_msg and self.fail_cb is not None:
                await self.fail_cb()


class GroupMsgChecker(MsgChecker):
    """群聊消息事件分级权限检查器

    基本功能与 :class:`MsgChecker` 一致。但增加了白名单机制，
    不提供 `white_groups` 参数默认拒绝所有群聊消息事件。

    对所有私聊消息事件校验不通过。
    """

    def __init__(
        self,
        role: LevelRole | GroupRole,
        owner: Optional[int] = None,
        super_users: Optional[Iterable[int]] = None,
        white_users: Optional[Iterable[int]] = None,
        black_users: Optional[Iterable[int]] = None,
        white_groups: Optional[Iterable[int]] = None,
        fail_cb: Optional[SyncOrAsyncCallable[[], None]] = None,
    ) -> None:
        """初始化一个群聊消息事件分级权限检查器

        :param role: 允许的等级（>= 此等级才能通过校验）
        :param owner: 主人的 qq 号
        :param super_users: 超级用户 qq 号
        :param white_users: 白名单用户 qq 号
        :param black_users: 黑名单用户 qq 号
        :param white_groups: 白名单群号（不在其中的群不通过校验）
        :param fail_cb: 检查不通过的回调
        """
        super().__init__(role, owner, super_users, white_users, black_users, fail_cb)
        self.white_group_list = tuple(white_groups) if white_groups is not None else ()
        self._hash_tag = (*self._hash_tag, self.white_group_list)

    def _check(self, event: MessageEvent) -> bool:
        # 不要使用 isinstace，避免通过反射模式注入的 event 依赖产生误判结果
        if event.is_private():
            return False
        if len(self.white_group_list) == 0:
            return False
        if cast(GroupMessageEvent, event).group_id not in self.white_group_list:
            return False
        return super()._check(event)


class PrivateMsgChecker(MsgChecker):
    """私聊消息事件分级权限检查器

    基本功能与 :class:`MsgChecker` 一致。

    对所有群聊消息事件校验不通过。
    """

    def __init__(
        self,
        role: LevelRole,
        owner: Optional[int] = None,
        super_users: Optional[Iterable[int]] = None,
        white_users: Optional[Iterable[int]] = None,
        black_users: Optional[Iterable[int]] = None,
        fail_cb: Optional[SyncOrAsyncCallable[[], None]] = None,
    ) -> None:
        """初始化一个私聊消息事件分级权限检查器

        :param role: 允许的等级（>= 此等级才能通过校验）
        :param owner: 主人的 qq 号
        :param super_users: 超级用户 qq 号
        :param white_users: 白名单用户 qq 号
        :param black_users: 黑名单用户 qq 号
        :param fail_cb: 检查不通过的回调
        """
        super().__init__(role, owner, super_users, white_users, black_users, fail_cb)

    def _check(self, event: MessageEvent) -> bool:
        if not event.is_private():
            return False
        return super()._check(event)


class MsgCheckerFactory:
    """消息事件分级权限检查器的工厂

    预先存储检查依据（各等级数据），指定检查等级后，可返回一个 :class:`MsgChecker` 类的对象
    """

    def __init__(
        self,
        owner: Optional[int] = None,
        super_users: Optional[Iterable[int]] = None,
        white_users: Optional[Iterable[int]] = None,
        black_users: Optional[Iterable[int]] = None,
        white_groups: Optional[Iterable[int]] = None,
        fail_cb: Optional[SyncOrAsyncCallable[[], None]] = None,
    ) -> None:
        """初始化一个消息事件分级权限检查器的工厂

        :param owner: 主人的 qq 号
        :param super_users: 超级用户 qq 号
        :param white_users: 白名单用户 qq 号
        :param black_users: 黑名单用户 qq 号
        :param white_groups: 白名单群号（不在其中的群不通过校验）
        :param fail_cb: 检查不通过的回调（这将自动附加到生成的检查器上）
        """
        self.owner = owner
        self.super_users = tuple(super_users) if super_users is not None else ()
        self.white_users = tuple(white_users) if white_users is not None else ()
        self.black_users = tuple(black_users) if black_users is not None else ()
        self.white_groups = tuple(white_groups) if white_groups is not None else ()

        self.fail_cb = fail_cb

    def get_base(
        self,
        role: LevelRole | GroupRole,
        fail_cb: Optional[SyncOrAsyncCallable[[], None]] = None,
    ) -> MsgChecker:
        """根据内部依据和给定等级，生成一个 :class:`MsgChecker` 对象

        :param role: 允许的等级（>= 此等级才能通过校验）
        :param fail_cb: 检查不通过的回调
        :return: 消息事件分级权限检查器
        """
        return MsgChecker(
            role,
            self.owner,
            self.super_users,
            self.white_users,
            self.black_users,
            self.fail_cb if fail_cb is None else fail_cb,
        )

    def get_group(
        self,
        role: LevelRole | GroupRole,
        fail_cb: Optional[SyncOrAsyncCallable[[], None]] = None,
    ) -> GroupMsgChecker:
        """根据内部依据和给定等级，生成一个 :class:`GroupMsgChecker` 对象

        :param role: 允许的等级（>= 此等级才能通过校验）
        :param fail_cb: 检查不通过的回调
        :return: 群聊消息事件分级权限检查器
        """
        return GroupMsgChecker(
            role,
            self.owner,
            self.super_users,
            self.white_users,
            self.black_users,
            self.white_groups,
            self.fail_cb if fail_cb is None else fail_cb,
        )

    def get_private(
        self,
        role: LevelRole,
        fail_cb: Optional[SyncOrAsyncCallable[[], None]] = None,
    ) -> PrivateMsgChecker:
        """根据内部依据和给定等级，生成一个 :class:`PrivateMsgChecker` 对象

        :param role: 允许的等级（>= 此等级才能通过校验）
        :param fail_cb: 检查不通过的回调
        :return: 私聊消息事件分级权限检查器
        """
        return PrivateMsgChecker(
            role,
            self.owner,
            self.super_users,
            self.white_users,
            self.black_users,
            self.fail_cb if fail_cb is None else fail_cb,
        )


class AtMsgChecker(Checker):
    """艾特消息事件检查器"""

    def __init__(
        self,
        qid: int | Literal["all"] | None = None,
        fail_cb: Optional[SyncOrAsyncCallable[[], None]] = None,
    ) -> None:
        """初始化一个艾特消息事件检查器

        :param qid: 被艾特的 qq 号。为空则接受所有艾特消息事件；不为空则只接受指定 qid 被艾特的艾特消息事件
        :param fail_cb: 检查不通过的回调
        """
        super().__init__(fail_cb)
        self.qid = qid
        self._hash_tag = qid

    async def check(self, event: Event) -> bool:
        # 不要使用 isinstace，避免通过反射模式注入的 event 依赖产生误判结果
        status = is_msg = False
        try:
            ret, is_msg = event.flag_get(
                self.__class__, self._hash_tag, raise_exc=False, default=(None, False)
            )
            if ret is not None:
                return cast(bool, ret)

            if not event.is_message():
                status = is_msg = False
            else:
                is_msg = True
                event = cast(MessageEvent, event)
                qids = [seg.data["qq"] for seg in event.message if isinstance(seg, AtSegment)]
                if self.qid is None:
                    status = len(qids) > 0
                else:
                    status = any(id == self.qid for id in qids)

            event.flag_set(self.__class__, self._hash_tag, (status, is_msg))
            return status

        finally:
            if not status and is_msg and self.fail_cb is not None:
                await self.fail_cb()
