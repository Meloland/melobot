from ..interface.typing import *
from ..interface.utils import BotChecker
from ..models.event import MsgEvent

__all__ = (
    'BotChecker',
    'MsgAccessChecker'
)


class MsgAccessChecker(BotChecker):
    """
    普通消息权限校验器，会过滤配置中非白名单群聊的消息。
    并根据配置中的权限列表，对 event 进行权限检查
    """
    def __init__(self, level: UserLevel, owner: int, super_users: List[int], white_users: List[int], black_users: List[int],
                 white_groups: List[int]
                 ) -> None:
        super().__init__()
        self.owner = owner
        self.su_list = super_users
        self.white_list = white_users
        self.black_list = black_users
        
        self.check_level = level
        self.white_group_list = white_groups

    def check(self, event: MsgEvent) -> bool:
        """
        不低于 level 级的 event 才会被接受。
        如果是群聊，还需要在白名单群列表内才会接受
        """
        e_level = self._get_level(event)
        if event.is_group() and event.group_id not in self.white_group_list:
            return False
        
        return 0 < e_level.value and e_level.value >= self.check_level.value
        

    def _get_level(self, event: MsgEvent) -> UserLevel:
        qid = event.sender.id

        if qid in self.black_list:
            return UserLevel.BLACK
        elif qid == self.owner:
            return UserLevel.OWNER
        elif qid in self.su_list:
            return UserLevel.SU
        elif qid in self.white_list:
            return UserLevel.WHITE
        else:
            return UserLevel.USER

