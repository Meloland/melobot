from .globalPattern import *
from .globalData import BOT_STORE
from abc import abstractclassmethod, ABC
from typing import NewType, Tuple, Union

UserLevel = NewType('UserLevel', int)
# 权限等级
SYS = UserLevel(101)
OWNER = UserLevel(100)
SU = UserLevel(90)
WHITE = UserLevel(80)
USER = UserLevel(70)
BLACK = UserLevel(-1)


class BaseAuthChecker(ABC):
    """
    权限校验器基类，所有权限校验器子类应该实现 check 方法
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

    # 响应事件判断
    def isResp(self, event: dict) -> bool: return 'retcode' in event.keys()
    # 元上报判断
    def isMetaReport(self, event: dict) -> bool: return event['post_type'] == 'meta_event'
    # 请求上报判断
    def isReqReport(self, event: dict) -> bool: return event['post_type'] == 'request'
    # 通知上报判断
    def isNoticeReport(self, event: dict) -> bool: return event['post_type'] == 'notice'
    # 消息上报判断
    def isMsgReport(self, event: dict) -> bool: return event['post_type'] == 'message'
    
    @abstractclassmethod
    def check(self, threshold_lvl: int, event: dict):
        pass


class MsgAuthChecker(BaseAuthChecker, Singleton):
    """
    分级权限校验器，只适用于消息事件
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

    def get_event_lvl(self, event: dict) -> UserLevel:
        """
        获得消息事件发起者的权限级别
        """
        the_id, msg_subtype = event['user_id'], event['sub_type']

        # 黑名单身份判断
        if the_id in self.black_ids:
            return BLACK
        # 如果群聊匿名，直接等价黑名单
        if msg_subtype == 'anonymous':
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

    def check(self, threshold_lvl: UserLevel, event: dict) -> bool:
        """
        消息事件权限检查
        """
        e_lvl = self.get_event_lvl(event)
        msg_type = event['message_type']

        # 组别检查
        if msg_type == 'group':
            if event['group_id'] not in self.group_ids:
                return False
        # 等级检查
        return 0 < e_lvl and e_lvl >= threshold_lvl


class NoticeAuthChecker(BaseAuthChecker, Singleton):
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
    
    def get_event_lvl(self, the_id: Union[int, str]) -> UserLevel:
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

    def check(self, condition: Tuple[str, UserLevel], event: dict) -> bool:
        """
        检查通知事件的 id 类属性，在 UserLevel 级是否合法。
        """
        lvl = self.get_event_lvl(event[condition[0]])
        return 0 < lvl and lvl >= condition[1]


MSG_CHECKER = MsgAuthChecker(BOT_STORE['custom']['OWNER'], \
    BOT_STORE['custom']['SUPER_USER'], \
    BOT_STORE['custom']['WHITE_LIST'], \
    BOT_STORE['custom']['BLACK_LIST'], \
    BOT_STORE['custom']['WHITE_GROUP_LIST'], \
)
NOTICE_CHECKER =  NoticeAuthChecker(BOT_STORE['custom']['OWNER'], \
    BOT_STORE['custom']['SUPER_USER'], \
    BOT_STORE['custom']['WHITE_LIST'], \
    BOT_STORE['custom']['BLACK_LIST'], \
    BOT_STORE['custom']['WHITE_GROUP_LIST'], \
)

