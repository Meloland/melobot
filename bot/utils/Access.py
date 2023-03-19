from common.Event import BotEvent
from common.Store import BOT_STORE
from common.Typing import *
from abc import ABC



# 权限等级
SYS = UserLevel(101)
OWNER = UserLevel(100)
SU = UserLevel(90)
WHITE = UserLevel(80)
USER = UserLevel(70)
BLACK = UserLevel(-1)


class BaseAuthChecker(ABC):
    """
    权限校验器基类
    """
    def __init__(self) -> None:
        super().__init__()
        self.auth_str_map = {
            SYS: 'sys',
            OWNER: 'owner',
            SU: 'superuser',
            WHITE: 'white',
            USER: 'user',
            BLACK: 'black'
        }

class MsgAuthChecker(BaseAuthChecker):
    """
    分级权限校验器，只适用于消息事件
    """
    def __init__(
        self, 
        owner_id: int, 
        su_ids: List[int],
        white_ids: List[int], 
        black_ids: List[int],
        group_ids: List[int]
    ) -> None:
        super().__init__()
        self.owner_id = owner_id
        self.su_ids = su_ids
        self.white_ids = white_ids
        self.black_ids = black_ids
        self.group_ids = group_ids

    def get_event_lvl(self, event: BotEvent) -> UserLevel:
        """
        获得消息事件发起者的权限级别
        """
        the_id = event.msg.sender.id

        # 黑名单身份判断
        if the_id in self.black_ids:
            return BLACK
        # 如果群聊匿名，直接等价黑名单
        if event.msg.is_group_anonym():
            return BLACK
        # 直接身份判断
        if the_id == self.owner_id:
            return OWNER
        if the_id in self.su_ids:
            return SU
        if the_id in self.white_ids:
            return WHITE
        else:
            return USER

    def check(self, threshold_lvl: UserLevel, event: BotEvent) -> bool:
        """
        消息事件权限检查
        """
        e_lvl = self.get_event_lvl(event)

        # 组别检查
        if event.msg.is_group():
            if event.msg.group_id not in self.group_ids:
                return False
        # 等级检查
        return 0 < e_lvl and e_lvl >= threshold_lvl


class NoticeAuthChecker(BaseAuthChecker):
    """
    通知事件权限校验器
    """
    def __init__(self, owner_id: str, su_ids: list, \
                white_ids: list, black_ids: list, \
                group_ids: list) -> None:
        super().__init__()
        self.owner_id = owner_id
        self.su_ids = su_ids
        self.white_ids = white_ids
        self.black_ids = black_ids
        self.group_ids = group_ids
    
    def get_event_lvl(self, the_id: int) -> UserLevel:
        """
        获得权限级别
        """
        # 黑名单身份判断
        if the_id in self.black_ids:
            return BLACK
        # 直接身份判断
        if the_id == self.owner_id:
            return OWNER
        if the_id in self.su_ids:
            return SU
        if the_id in self.white_ids:
            return WHITE
        else:
            return USER

    def check(self, threshold_lvl: UserLevel, the_id: int) -> bool:
        """
        检查通知事件的 id 类属性，在 UserLevel 级是否合法。
        """
        lvl = self.get_event_lvl(the_id)
        return 0 < lvl and lvl >= threshold_lvl


MSG_CHECKER = MsgAuthChecker(BOT_STORE.config.owner, \
    BOT_STORE.config.super_user, \
    BOT_STORE.config.white_list, \
    BOT_STORE.config.black_list, \
    BOT_STORE.config.white_group_list, \
)
NOTICE_CHECKER =  NoticeAuthChecker(BOT_STORE.config.owner, \
    BOT_STORE.config.super_user, \
    BOT_STORE.config.white_list, \
    BOT_STORE.config.black_list, \
    BOT_STORE.config.white_group_list, \
)

