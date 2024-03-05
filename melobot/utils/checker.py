import re

from ..models.event import MessageEvent, MetaEvent, NoticeEvent, RequestEvent
from ..types.exceptions import *
from ..types.typing import *
from ..types.utils import BotChecker


class MsgLvlChecker(BotChecker):
    """
    消息分级权限校验器，不低于预设等级的 event 才会被接受。
    """

    def __init__(
        self,
        level: User,
        owner: int = None,
        super_users: List[int] = None,
        white_users: List[int] = None,
        black_users: List[int] = None,
    ) -> None:
        super().__init__()
        self.check_lvl = level

        self.owner = owner
        self.su_list = super_users if super_users is not None else []
        self.white_list = white_users if white_users is not None else []
        self.black_list = black_users if black_users is not None else []

    def _get_level(self, event: MessageEvent) -> User:
        """
        获得事件对应的登记
        """
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

    def check(self, event: MessageEvent) -> bool:
        """
        消息校验
        """
        e_level = self._get_level(event)
        return 0 < e_level.value and e_level.value >= self.check_lvl.value


class GroupMsgLvl(MsgLvlChecker):
    """
    群聊消息分级权限检查器，不低于预设等级的 event 才会被接受。
    不接受非白名单群聊的消息，也不接受任何私聊消息。
    特别注意：如果 white_groups 参数为 None，不启用白名单群聊校验
    """

    def __init__(
        self,
        level: User,
        owner: int = None,
        super_users: List[int] = None,
        white_users: List[int] = None,
        black_users: List[int] = None,
        white_groups: List[int] = None,
    ) -> None:
        super().__init__(level, owner, super_users, white_users, black_users)
        self.white_group_list = white_groups if white_groups is not None else []

    def check(self, event: MessageEvent) -> bool:
        if not event.is_group():
            return False
        if len(self.white_group_list) == 0:
            return False
        if event.group_id not in self.white_group_list:
            return False
        return super().check(event)


class PrivateMsgLvl(MsgLvlChecker):
    """
    私聊消息分级权限检查器，不低于预设等级的 event 才会被接受。不接受任何群聊消息
    """

    def __init__(
        self,
        level: User,
        owner: int = None,
        super_users: List[int] = None,
        white_users: List[int] = None,
        black_users: List[int] = None,
    ) -> None:
        super().__init__(level, owner, super_users, white_users, black_users)

    def check(self, event: MessageEvent) -> bool:
        if not event.is_private():
            return False
        return super().check(event)


class MsgCheckerGen:
    """
    消息校验器生成器。预先存储校验依据（各等级数据），
    指定校验 level 后返回一个符合 MsgLvlChecker 接口的实例对象
    """

    def __init__(
        self,
        owner: int = None,
        super_users: List[int] = None,
        white_users: List[int] = None,
        black_users: List[int] = None,
        white_groups: List[int] = None,
    ) -> None:
        self.owner = owner
        self.su_list = super_users if super_users is not None else []
        self.white_list = white_users if white_users is not None else []
        self.black_list = black_users if black_users is not None else []
        self.white_group_list = white_groups if white_groups is not None else []

    def gen_base(self, level: User = User.USER) -> MsgLvlChecker:
        """
        根据内部依据，生成一个原始消息等级校验器
        """
        return MsgLvlChecker(
            level, self.owner, self.su_list, self.white_list, self.black_list
        )

    def gen_group(self, level: User = User.USER) -> GroupMsgLvl:
        """
        根据内部依据，生成一个群组消息等级校验器
        """
        return GroupMsgLvl(
            level,
            self.owner,
            self.su_list,
            self.white_list,
            self.black_list,
            self.white_group_list,
        )

    def gen_private(self, level: User = User.USER) -> PrivateMsgLvl:
        """
        根据内部依据，生成一个私聊消息等级校验器
        """
        return PrivateMsgLvl(
            level, self.owner, self.su_list, self.white_list, self.black_list
        )


class AtChecker(BotChecker):
    """
    at 消息校验器。
    如果事件中包含指定 qid 的 at 消息，则校验结果为真
    """

    def __init__(self, qid: int = None) -> None:
        self.qid = str(qid) if qid is not None else None
        self._cq_at_regex = re.compile(r"\[CQ:at,qq=(\d+)?\]")

    def check(self, event: MessageEvent) -> bool:
        """
        当 qid 为空时，只要有 at 消息就通过校验。
        如果不为空，则必须出现指定 qid 的 at 消息
        """
        id_list = self._cq_at_regex.findall(event.raw_content)
        if self.qid is None:
            return len(id_list) > 0
        for id in id_list:
            if id == self.qid:
                return True
        return False


class FriendReqChecker(BotChecker):
    """
    朋友请求事件校验器。
    如果事件是来自朋友的请求事件，则校验结果为真
    """

    def __init__(self) -> None:
        super().__init__()

    def check(self, event: RequestEvent) -> bool:
        return event.is_friend_req()


class GroupReqChecker(BotChecker):
    """
    群请求事件校验器。
    如果事件是来自群的请求事件，则校验结果为真
    """

    def __init__(self) -> None:
        super().__init__()

    def check(self, event: RequestEvent) -> bool:
        return event.is_group_req()


class NoticeTypeChecker(BotChecker):
    """
    通知事件类型校验器。
    校验是否为指定通知类型的通知事件
    """

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
        super().__init__()
        if sub_type not in NoticeTypeChecker.SUB_TYPES:
            raise BotCheckerError(f"通知事件类型校验器的子类型 {sub_type} 不合法")
        self.sub_type = sub_type

    def check(self, event: NoticeEvent) -> bool:
        if self.sub_type == "ALL":
            return True
        check_method = getattr(event, "is_" + self.sub_type)
        return check_method()
