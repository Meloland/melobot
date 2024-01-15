from ..interface.typing import *
from ..interface.utils import BotChecker
from ..models.event import MsgEvent


class MsgLvlChecker(BotChecker):
    """
    消息分级权限校验器，不低于预设等级的 event 才会被接受。
    """
    def __init__(self, level: User, owner: int=None, super_users: List[int]=None, white_users: List[int]=None, 
                 black_users: List[int]=None) -> None:
        super().__init__()
        self.check_lvl = level
        self.owner = owner

        self.su_list = super_users if super_users is not None else []
        self.white_list = white_users if white_users is not None else []
        self.black_list = black_users if black_users is not None else []

    def _get_level(self, event: MsgEvent) -> User:
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

    def check(self, event: MsgEvent) -> bool:
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
    def __init__(self, level: User, owner: int=None, super_users: List[int]=None, white_users: List[int]=None, 
                 black_users: List[int]=None, white_groups: List[int]=None) -> None:
        super().__init__(level, owner, super_users, white_users, black_users)
        self.white_group_list = white_groups

    def check(self, event: MsgEvent) -> bool:
        if not event.is_group():
            return False
        if self.white_group_list \
                and event.is_group() \
                and event.group_id not in self.white_group_list:
            return False
        return super().check(event)


class PrivateMsgLvl(MsgLvlChecker):
    """
    私聊消息分级权限检查器，不低于预设等级的 event 才会被接受。不接受任何群聊消息
    """
    def __init__(self, level: User, owner: int=None, super_users: List[int]=None, white_users: List[int]=None, 
                 black_users: List[int]=None) -> None:
        super().__init__(level, owner, super_users, white_users, black_users)

    def check(self, event: MsgEvent) -> bool:
        if not event.is_private():
            return False
        return super().check(event)
