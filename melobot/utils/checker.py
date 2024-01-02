from ..interface.typing import *
from ..interface.utils import BotChecker
from ..models.event import MsgEvent


class MsgAccessChecker(BotChecker):
    """
    普通消息权限校验器，会过滤配置中非白名单群聊的消息。
    并根据配置中的权限列表，对 event 进行权限检查。
    特别注意：当 white_groups 为空时，不启用白名单群聊校验
    """
    def __init__(self, level: UserLevel, owner: int=None, super_users: List[int]=None, white_users: List[int]=None, 
                 black_users: List[int]=None, white_groups: List[int]=None
                 ) -> None:
        super().__init__()
        self.owner = owner
        self.su_list = super_users
        self.white_list = white_users
        self.black_list = black_users

        if self.su_list is None: self.su_list = []
        if self.white_list is None: self.white_list = []
        if self.black_list is None: self.black_list = []
        
        self.check_level = level
        self.white_group_list = white_groups

    def check(self, event: MsgEvent) -> bool:
        """
        不低于 level 级的 event 才会被接受。
        如果是群聊，还需要在白名单群列表内才会接受
        """
        e_level = self._get_level(event)
        if self.white_group_list \
                and event.is_group() \
                and event.group_id not in self.white_group_list:
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

