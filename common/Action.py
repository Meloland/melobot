import json
from . import Encoder as ec
from .Event import *
from .Global import *
from .Exceptions import *
from .Snowflake import ID_WORKER
from .Typing import *
from abc import ABC


__all__ = [
    'BotAction', 

    # 消息构造方法
    'text_msg', 
    'face_msg', 
    'record_msg', 
    'at_msg', 
    'share_msg', 
    'music_msg', 
    'custom_music_msg', 
    'image_msg', 
    'reply_msg', 
    'poke_msg', 
    'tts_msg',

    # cq 编码相关
    'cq_escape', 
    'cq_anti_escape',
    
    # 消息发送、处理相关
    'msg_action', 
    'forward_msg_action', 
    'custom_msg_node', 
    'refer_msg_node',
    'msg_del_action',
    'get_msg_action',
    'get_forward_msg_action',
    'mark_msg_read_action',
    
    # 群相关
    'group_kick_action',
    'group_ban_action',
    'group_anonym_ban_action',
    'group_whole_ban_action',
    'group_leave_action',
    'group_sign_action',
    'get_group_info_action',
    'get_group_list_action',
    'get_group_member_info_action',
    'get_group_member_list_action',
    'get_group_honor_action',
    'get_group_filesys_info_action',
    'get_group_root_files_action',
    'get_group_files_byfolder_action',
    'get_group_file_url_action',
    'get_group_sys_msg_action',
    'get_group_notice_action',
    'get_group_msg_history_action',
    'get_group_essence_list_action',
    'set_group_admin_action',
    'set_group_card_action',
    'set_group_name_action',
    'set_group_title_action',
    'set_group_add_action',
    'set_group_portrait_action',
    'set_group_notice_action',
    'set_group_essence_action',
    'create_group_folder_action',
    'delete_group_folder_action',
    'delete_group_file_action',
    
    # 私聊相关
    'get_friend_list_action',
    'get_undirect_friend_action',
    'get_stranger_info_action',
    'set_friend_add_action',
    'delete_friend_action',
    'delete_undirect_friend_action',
    
    # bot 前后端相关
    'get_login_info_action',
    'set_login_profile_action',
    'check_send_image_action',
    'check_send_record_action',
    'get_cq_status_action',
    'get_cq_version_action',
    'quick_handle_action',
    
    # 其他操作
    'get_image_action',
    'download_file_action',
    'ocr_action',
    'upload_file_action',
    'get_atall_remain_action',
    
    # 登录设备和机型相关
    'get_online_clients_action',
    'get_model_show_action',
    'set_model_show_action',
    
]


# 用于 msg action 构造的一些函数
text_msg = ec.text
face_msg = ec.face
record_msg = ec.record
at_msg = ec.at
share_msg = ec.share
music_msg = ec.music
custom_music_msg = ec.custom_music
image_msg = ec.image
reply_msg = ec.reply
poke_msg = ec.poke
tts_msg = ec.tts
cq_escape = ec.escape
cq_anti_escape = ec.anti_escape


class ActionPack(ABC): 
    """
    行为信息构造基类
    """
    def __init__(self) -> None:
        super().__init__()
        self.type: str
        self.params: dict


class BotAction:
    """
    Bot 行为类
    """
    def __init__(
        self, 
        package: ActionPack,
        respWaited: bool=False, 
        triggerEvent: BotEvent=None
    ) -> None:
        # 只有 action 对应的 resp 需要被等待单独处理时（即不参与常规的事件调度），才会生成 id
        self.respId: Union[str, None] = str(ID_WORKER.get_id()) if respWaited else None
        self.type: str = package.type
        self.params: dict = package.params
        self.trigger_e: Union[BotEvent, None] = triggerEvent

    def extract(self) -> dict:
        """
        从对象提取标准 cq action
        """
        obj = {
            'action': self.type,
            "params": self.params,
        }
        if self.respId: obj['echo'] = self.respId
        return obj

    def flatten(self) -> str:
        """
        将对象序列化为标准 cq action json 字符串，一般供连接器使用
        """
        return json.dumps(self.extract(), ensure_ascii=False)


class MsgPack(ActionPack):
    """
    消息 action 信息构造类
    """
    def __init__(
        self, 
        msgs: MsgSegment,
        isPrivate: bool, 
        userId: int, 
        groupId: int=None, 
    ) -> None:
        super().__init__()
        self.type = 'send_msg'
        if isPrivate:
            self.params = {
                'message_type': 'private',
                'user_id': userId,
                'message': msgs,
            }
        else:
            self.params = {
                'message_type': 'group',
                'user_id': userId,
                'group_id': groupId,
                'message': msgs,
            }

def msg_action(
    content: Union[str, ec.Msg, MsgSegment],
    isPrivate: bool,
    userId: int, 
    groupId: int=None,
    respWaited: bool=False,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    发送消息 action 构造方法
    """
    if isinstance(content, str):
        msgs = ec.text(content)
        if not isinstance(msgs, list):
            msgs = [msgs]
    elif isinstance(content, dict):
        msgs = [content]
    elif isinstance(content, list):
        temp = []
        for _ in content:
            if isinstance(_, list):
                temp.extend(_)
            else:
                temp.append(_)
        msgs = temp
    else:
        raise BotUnexpectFormat("消息格式不正确，无法封装")
    return BotAction(
        MsgPack(
            msgs, isPrivate, userId, groupId
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class ForwardMsgPack(ActionPack):
    """
    转发消息 action 信息构造类
    """
    def __init__(
        self,
        msgs: MsgNodeList,
        isPrivate: bool,
        userId: int=None,
        groupId: int=None,
    ) -> None:
        super().__init__()
        if isPrivate:
            self.type = 'send_private_forward_msg'
            self.params = {
                'user_id': userId,
                'messages': msgs
            }
        else:
            self.type = 'send_group_forward_msg'
            self.params = {
                'group_id': groupId,
                'messages': msgs
            }

def custom_msg_node(
    content: Union[str, ec.Msg, MsgSegment], 
    sendName:str, 
    sendId: int,
    seq: str=None,
) -> MsgNode:
    """
    自定义消息节点构造方法。转化字符串、消息、消息段为消息节点
    """
    if isinstance(content, str):
        msgs = ec.text(content)
        if not isinstance(msgs, list):
            msgs = [msgs]
    elif isinstance(content, dict):
        msgs = [content]
    elif isinstance(content, list):
        temp = []
        for _ in content:
            if isinstance(_, list):
                temp.extend(_)
            else:
                temp.append(_)
        msgs = temp
    ret = {
        "type": "node", 
        "data": {
            "name": sendName,
            "uin": str(sendId),
            "content": msgs
        }
    }
    if seq: ret['data']['seq'] = seq
    return ret

def refer_msg_node(msgId: int) -> MsgNode:
    """
    引用消息节点构造方法
    """
    return {
        "type": "node",
        "data": {
            "id": str(msgId)
        }
    }

def forward_msg_action(
    msgNodes: MsgNodeList,
    isPrivate: bool,
    userId: int=None, 
    groupId: int=None,
    respWaited: bool=False,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    转发消息发送 action 构造方法
    """
    return BotAction(
        ForwardMsgPack(
            msgNodes, isPrivate, userId, groupId
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class MsgDelPack(ActionPack):
    """
    撤回消息 action 信息构造类
    """
    def __init__(self, msgId: int) -> None:
        super().__init__()
        self.type = 'delete_msg'
        self.params = {
            'message_id': msgId,
        }

def msg_del_action(
    msgId: int,
    respWaited: bool=False,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    撤回消息 action 构造方法
    """
    return BotAction(
        MsgDelPack(msgId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetMsgPack(ActionPack):
    """
    消息信息获取 action 信息构造类
    """
    def __init__(self, msgId: int) -> None:
        super().__init__()
        self.type = 'get_msg'
        self.params = {
            'message_id': msgId
        }
    
def get_msg_action(
    msgId: int,
    respWaited: bool=True,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    获取消息详细信息 action 构造方法
    """
    return BotAction(
        GetMsgPack(msgId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class getForwardPack(ActionPack):
    """
    转发消息获取 action 信息构造类
    """
    def __init__(self, forwardId: str) -> None:
        super().__init__()
        self.type = 'get_forward_msg'
        self.params = {
            'message_id': forwardId
        }

def get_forward_msg_action(
    forwardId: str,
    respWaited: bool=True,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    转发消息获取 action 构造方法
    """
    return BotAction(
        getForwardPack(forwardId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class getImagePack(ActionPack):
    """
    获取图片信息 action 信息构造类
    """
    def __init__(self, fileName: str) -> None:
        super().__init__()
        self.type = 'get_image'
        self.params = {
            'file': fileName
        }

def get_image_action(
    fileName: str,
    respWaited: bool=True,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    获取图片信息 action 构造方法
    """
    return BotAction(
        getImagePack(fileName),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class MarkMsgReadPack(ActionPack):
    """
    标记消息已读 action 信息构造类
    """
    def __init__(self, msgId: int) -> None:
        super().__init__()
        self.type = 'mark_msg_as_read'
        self.params = {
            'message_id': msgId
        }

def mark_msg_read_action(
    msgId: int,
    respWaited: bool=False,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    标记消息已读 action 构造方法
    """
    return BotAction(
        MarkMsgReadPack(msgId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GroupKickPack(ActionPack):
    """
    群组踢人 action 信息构造类
    """
    def __init__(
        self, 
        groupId: int, 
        userId: int, 
        laterReject: bool=False
    ) -> None:
        super().__init__()
        self.type = 'set_group_kick'
        self.params = {
            "group_id": groupId,
            "user_id": userId,
            "reject_add_request": laterReject
        }

def group_kick_action(
    groupId: int, 
    userId: int, 
    laterReject: bool=False,
    respWaited: bool=False,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    群组踢人 action 构造方法
    """
    return BotAction(
        GroupKickPack(
            groupId, userId, laterReject
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GroupBanPack(ActionPack):
    """
    群组禁言 action 信息构造类
    """
    def __init__(
        self,
        groupId: int,
        userId: int,
        duration: int
    ) -> None:
        super().__init__()
        self.type = 'set_group_ban'
        self.params = {
            'group_id': groupId,
            'user_id': userId,
            'duration': duration,
        }

def group_ban_action(
    groupId: int,
    userId: int,
    duration: int,
    respWaited: bool=False,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    群组禁言 action 构造方法。
    duration 为 0 取消禁言
    """
    return BotAction(
        GroupBanPack(
            groupId, userId, duration
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GroupAnonymBanPack(ActionPack):
    """
    群组匿名禁言 action 信息构造类
    """
    def __init__(
        self,
        groupId: int,
        anonymFlag: str,
        duration: int
    ) -> None:
        super().__init__()
        self.type = 'set_group_anonymous_ban'
        self.params = {
            'group_id': groupId,
            'anonymous_flag': anonymFlag,
            'duration': duration,
        }

def group_anonym_ban_action(
    groupId: int,
    anonymFlag: str,
    duration: int,
    respWaited: bool=False,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    群组匿名禁言 action 构造方法。
    无法取消禁言
    """
    return BotAction(
        GroupAnonymBanPack(
            groupId, anonymFlag, duration
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GroupWholeBanPack(ActionPack):
    """
    群组全员禁言 action 信息构造类
    """
    def __init__(
        self,
        groupId: int,
        enable: bool
    ) -> None:
        super().__init__()
        self.type = 'set_group_whole_ban'
        self.params = {
            'group_id': groupId,
            'enable': enable
        }

def group_whole_ban_action(
    groupId: int,
    enable: bool,
    respWaited: bool=False,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    群组全员禁言 action 构造方法
    """
    return BotAction(
        GroupWholeBanPack(
            groupId, enable
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class SetGroupAdminPack(ActionPack):
    """
    设置群管理员 action 信息构造类
    """
    def __init__(
        self,
        groupId: int,
        userId: int,
        enable: bool
    ) -> None:
        super().__init__()
        self.type = 'set_group_admin'
        self.params = {
            'group_id': groupId,
            'user_id': userId,
            'enable': enable
        }
    
def set_group_admin_action(
    groupId: int,
    userId: int,
    enable: bool,
    respWaited: bool=False,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    设置群管理员 action 构造方法
    """
    return BotAction(
        SetGroupAdminPack(
            groupId, userId, enable
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class SetGroupCard(ActionPack):
    """
    设置群名片 action 信息构造类
    """
    def __init__(
        self,
        groupId: int,
        userId: int,
        card: str
    ) -> None:
        super().__init__()
        self.type = 'set_group_card'
        self.params = {
            'group_id': groupId,
            'user_id': userId,
            'card': card
        }

def set_group_card_action(
    groupId: int,
    userId: int,
    card: str,
    respWaited: bool=False,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    设置群名片 action 构造方法
    """
    return BotAction(
        SetGroupCard(groupId, userId, card),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class SetGroupName(ActionPack):
    """
    设置群名 action 信息构造类
    """
    def __init__(
        self,
        groupId: int,
        name: str
    ) -> None:
        super().__init__()
        self.type = 'set_group_name'
        self.params = {
            'group_id': groupId,
            'group_name': name
        }
    
def set_group_name_action(
    groupId: int,
    name: str,
    respWaited: bool=False,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    设置群名 action 信息构造方法
    """
    return BotAction(
        SetGroupName(groupId, name),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GroupLeavePack(ActionPack):
    """
    退出群组 action 信息构造类
    """
    def __init__(
        self,
        groupId: int,
        isDismiss: bool
    ) -> None:
        super().__init__()
        self.type = 'set_group_leave'
        self.params = {
            'group_id': groupId,
            'is_dismiss': isDismiss
        }

def group_leave_action(
    groupId: int,
    isDismiss: bool,
    respWaited: bool=False,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    退出群组 action 构造方法
    """
    return BotAction(
        GroupLeavePack(
            groupId, isDismiss
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class SetGroupTitlePack(ActionPack):
    """
    设置群头衔 action 信息构造类
    """
    def __init__(
        self,
        groupId: int,
        userId: int,
        title: str,
        duration: int=-1,
    ) -> None:
        super().__init__()
        self.type = 'set_group_special_title'
        self.params = {
            'group_id': groupId,
            'user_id': userId,
            'special_title': title, 
            'duration': duration
        }

def set_group_title_action(
    groupId: int,
    userId: int,
    title: str,
    duration: int=-1,
    respWaited: bool=False,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    设置群头衔 action 构造方法
    """
    return BotAction(
        SetGroupTitlePack(
            groupId, userId, title, duration
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GroupSignPack(ActionPack):
    """
    群打卡 action 信息构造类
    """
    def __init__(
        self,
        groupId: int
    ) -> None:
        super().__init__()
        self.type = 'send_group_sign'
        self.params = {
            'group_id': groupId
        }

def group_sign_action(
    groupId: int,
    respWaited: bool=False,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    群打卡 action 构造方法
    """
    return BotAction(
        GroupSignPack(groupId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class SetFriendAddPack(ActionPack):
    def __init__(
        self,
        addFlag: str,
        approve: bool,
        remark: str
    ) -> None:
        """
        处理加好友请求 action 信息构造类
        """
        super().__init__()
        self.type = 'set_friend_add_request'
        self.params = {
            'flag': addFlag,
            'approve': approve,
            'remark': remark
        }

def set_friend_add_action(
    addFlag: str,
    approve: bool,
    remark: str,
    respWaited: bool=False,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    处理加好友信息 action 构造方法。注意 remark 目前暂未实现
    """
    return BotAction(
        SetFriendAddPack(
            addFlag, approve, remark
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )
        

class SetGroupAddPack(ActionPack):
    """
    处理加群请求 action 信息构造类
    """
    def __init__(
        self,
        addFlag: str,
        addType: Literal['add', 'invite'],
        approve: bool,
        reason: str=None
    ) -> None:
        super().__init__()
        self.type = 'set_group_add_request'
        self.params = {
            'flag': addFlag,
            'sub_type': addType,
            'approve': approve,
        }
        if reason: self.params['reason'] = reason
    
def set_group_add_action(
    addFlag: str,
    addType: Literal['add', 'invite'],
    approve: bool,
    rejectReason: str=None,
    respWaited: bool=False,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    处理加群请求 action 构造方法
    """
    return BotAction(
        SetGroupAddPack(
            addFlag, addType, approve, rejectReason
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetLoginInfoPack(ActionPack):
    """
    获取登录号信息 action 信息构造类
    """
    def __init__(self) -> None:
        super().__init__()
        self.type = 'get_login_info'
        self.params = {}

def get_login_info_action(
    respWaited: bool=True,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    获得登录号信息 action 构造方法
    """
    return BotAction(
        GetLoginInfoPack(),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class SetLoginProfilePack(ActionPack):
    """
    设置登录号资料 action 信息构造类
    """
    def __init__(
        self,
        nickname: str,
        company: str,
        email: str,
        college: str,
        personalNote: str
    ) -> None:
        super().__init__()
        self.type = 'set_qq_profile'
        self.params = {
            'nickname': nickname,
            'company': company,
            'email': email,
            'college': college,
            'personal_note': personalNote
        }

def set_login_profile_action(
    nickname: str,
    company: str,
    email: str,
    college: str,
    personalNote: str,
    respWaited: bool=False,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    设置登录号资料 action 构造方法
    """
    return BotAction(
        SetLoginProfilePack(
            nickname, company, email, college, personalNote
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )

        
class GetStrangerInfoPack(ActionPack):
    """
    获取陌生人信息 action 信息构造类
    """
    def __init__(
        self,
        userId: int,
        noCache: bool
    ) -> None:
        super().__init__()
        self.type = 'get_stranger_info'
        self.params = {
            'user_id': userId,
            'no_cache': noCache
        }

def get_stranger_info_action(
    userId: int,
    noCache: bool,
    respWaited: bool=True,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    获取陌生人信息 action 构造方法。也可以对好友使用
    """
    return BotAction(
        GetStrangerInfoPack(
            userId, noCache
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetFriendListPack(ActionPack):
    """
    获取好友列表 action 信息构造类
    """
    def __init__(self) -> None:
        super().__init__()
        self.type = 'get_friend_list'
        self.params = {}

def get_friend_list_action(
    respWaited: bool=True,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    获取好友列表 action 构造方法
    """
    return BotAction(
        GetFriendListPack(),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetUndirectFriendPack(ActionPack):
    """
    获取单向好友列表 action 信息构造类
    """
    def __init__(self) -> None:
        super().__init__()
        self.type = 'get_unidirectional_friend_list'
        self.params = {}

def get_undirect_friend_action(
    respWaited: bool=True,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    获取单向好友信息列表 action 构造方法
    """
    return BotAction(
        GetUndirectFriendPack(),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class DeleteFriendPack(ActionPack):
    """
    删除好友 action 信息构造类
    """
    def __init__(
        self,
        userId: int
    ) -> None:
        super().__init__()
        self.type = 'delete_friend'
        self.params = {
            'user_id': userId
        }

def delete_friend_action(
    userId: int,
    respWaited: bool=False,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    删除好友 action 构造方法
    """
    return BotAction(
        DeleteFriendPack(userId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetGroupInfoPack(ActionPack):
    """
    获取群信息 action 信息构造类
    """
    def __init__(
        self,
        groupId: int,
        noCache: bool
    ) -> None:
        super().__init__()
        self.type = 'get_group_info'
        self.params = {
            'group_id': groupId,
            'no_cache': noCache
        }

def get_group_info_action(
    groupId: int,
    noCache: bool,
    respWaited: bool=True,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    获取群信息 action 构造方法。可以是未加入的群聊
    """
    return BotAction(
        GetGroupInfoPack(
            groupId, noCache
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetGroupListPack(ActionPack):
    """
    获取群列表 action 信息构造类
    """
    def __init__(self) -> None:
        super().__init__()
        self.type = 'get_group_list'
        self.params = {}

def get_group_list_action(
    respWaited: bool=True,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    获取群列表 action 构造方法。注意返回建群时间都是 0，这是不准确的。准确的建群时间可以通过 `get_group_info_action` 获得
    """
    return BotAction(
        GetGroupListPack(),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetGroupMemberInfoPack(ActionPack):
    """
    获取群成员信息 action 信息构造类
    """
    def __init__(
        self,
        groupId: int,
        userId: int,
        noCache: bool
    ) -> None:
        super().__init__()
        self.type = 'get_group_member_info'
        self.params = {
            'group_id': groupId,
            'user_id': userId,
            'no_cache': noCache
        }

def get_group_member_info_action(
    groupId: int,
    userId: int,
    noCache: bool,
    respWaited: bool=True,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    获取群成员信息 action 构造方法
    """
    return BotAction(
        GetGroupMemberInfoPack(
            groupId, userId, noCache
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetGroupMemberListPack(ActionPack):
    """
    获取群成员列表 action 信息构造类
    """
    def __init__(
        self,
        groupId: int,
        noCache: bool
    ) -> None:
        super().__init__()
        self.type = 'get_group_member_list'
        self.params = {
            'group_id': groupId,
            'no_cache': noCache
        }

def get_group_member_list_action(
    groupId: int,
    noCache: bool,
    respWaited: bool=True,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    获取群成员列表 action 构造方法
    """
    return BotAction(
        GetGroupMemberListPack(
            groupId, noCache
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetGroupHonorPack(ActionPack):
    """
    获取群荣誉信息 action 信息构造类
    """
    def __init__(
        self,
        groupId: int,
        type: Literal['talkative', 'performer', 'legend', 'strong_newbie', 'emotion', 'all']
    ) -> None:
        super().__init__()
        self.type = 'get_group_honor_info'
        self.params = {
            'group_id': groupId,
            'type': type
        }

def get_group_honor_action(
    groupId: int,
    type: Literal['talkative', 'performer', 'legend', 'strong_newbie', 'emotion', 'all'],
    respWaited: bool=True,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    获取群荣誉信息 action 构造方法
    """
    return BotAction(
        GetGroupHonorPack(
            groupId, type
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class CheckSendImagePack(ActionPack):
    """
    检查是否可以发送图片 action 信息构造类
    """
    def __init__(self) -> None:
        super().__init__()
        self.type = 'can_send_image'
        self.params = {}

def check_send_image_action(
    respWaited: bool=True,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    检查是否可以发送图片 action 构造方法
    """
    return BotAction(
        CheckSendImagePack(),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class CheckSendRecordPack(ActionPack):
    """
    检查是否可以发送语音 action 信息构造类
    """
    def __init__(self) -> None:
        super().__init__()
        self.type = 'can_send_image'
        self.params = {}

def check_send_record_action(
    respWaited: bool=True,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    检查是否可以发送语音 action 构造方法
    """
    return BotAction(
        CheckSendRecordPack(),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetCqVersionPack(ActionPack):
    """
    获取 go-cqhttp 版本信息 action 信息构造类
    """
    def __init__(self) -> None:
        super().__init__()
        self.type = 'get_version_info'
        self.params = {}

def get_cq_version_action(
    respWaited: bool=True,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    获取 go-cqhttp 版本信息 action 构造方法
    """
    return BotAction(
        GetCqVersionPack(),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class SetGroupPortraitPack(ActionPack):
    """
    设置群头像 action 信息构造类
    """
    def __init__(
        self,
        groupId: int,
        file: str,
        cache: Literal[0, 1]=0
    ) -> None:
        super().__init__()
        self.type = 'set_group_portrait'
        self.params = {
            'group_id': groupId,
            'file': file,
            'cache': cache
        }

def set_group_portrait_action(
    groupId: int,
    file: str,
    cache: Literal[0, 1]=0,
    respWaited: bool=False,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    设置群头像 action 构造方法。file 参数接受本地或网络 url 和 base64 编码。
    如本地路径为：`file:///C:/Users/Richard/Pictures/1.png`。
    特别注意：目前此 API 在登录一段时间后会因 cookie 失效而失效
    """
    return BotAction(
        SetGroupPortraitPack(
            groupId, file, cache
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class OcrPack(ActionPack):
    """
    图片 OCR action 信息构造类
    """
    def __init__(
        self,
        image: str
    ) -> None:
        super().__init__()
        self.type = 'ocr_image'
        self.params = {
            'image': image
        }

def ocr_action(
    image: str,
    respWaited: bool=True,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    图片 OCR action 构造方法。image 为图片 ID
    """
    return BotAction(
        OcrPack(image),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetGroupSysMsgPack(ActionPack):
    """
    获取群系统消息 action 信息构造类
    """
    def __init__(self) -> None:
        super().__init__()
        self.type = 'get_group_system_msg'
        self.params = {}

def get_group_sys_msg_action(
    respWaited: bool=True,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    获取群系统消息 action 构造方法
    """
    return BotAction(
        GetGroupSysMsgPack(),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class UploadFilePack(ActionPack):
    """
    发送文件 action 信息构造类
    """
    def __init__(
        self,
        isPrivate: bool,
        file: str,
        name: str,
        userId: int=None,
        groupId: int=None,
        groupFolderId: str=None
    ) -> None:
        super().__init__()
        if isPrivate:
            self.type = 'upload_private_file'
            self.params = {
                'user_id': userId,
                'file': file,
                'name': name
            }
        else:
            self.type = 'upload_group_file'
            self.params = {
                'group_id': groupId,
                'file': file,
                'name': name,
                'folder': groupFolderId
            }

def upload_file_action(
    isPrivate: bool,
    file: str,
    sendFileName: str,
    userId: int=None,
    groupId: int=None,
    groupFolderId: str=None,
    respWaited: bool=False,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    发送文件 action 构造方法。只支持发送本地文件。
    若为群聊文件发送，不提供 folder id，则默认上传到群文件根目录。
    
    示例路径：`C:/users/15742/desktop/QQ图片20230108225606.jpg`。
    
    （若需要发送网络文件，先使用 `download_file_action()` 方法生成下载网络文件的 action，
    action 响应后文件会放于 go-cqhttp 缓存文件夹中，可直接在消息段中引用）
    """
    return BotAction(
        UploadFilePack(
            isPrivate, file, sendFileName, userId, groupId, groupFolderId
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetGroupFileSysInfoPack(ActionPack):
    """
    获取群文件系统信息 action 信息构造类
    """
    def __init__(
        self,
        groupId: int
    ) -> None:
        super().__init__()
        self.type = 'get_group_file_system_info'
        self.params = {
            'group_id': groupId
        }

def get_group_filesys_info_action(
    groupId: int,
    respWaited: bool=True,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    获取群文件系统信息 action 构造方法
    """
    return BotAction(
        GetGroupFileSysInfoPack(groupId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetGroupRootFilesPack(ActionPack):
    """
    获取群根目录文件列表 action 信息构造类
    """
    def __init__(
        self,
        groupId: int
    ) -> None:
        super().__init__()
        self.type = 'get_group_root_files'
        self.params = {
            'group_id': groupId
        }

def get_group_root_files_action(
    groupId: int,
    respWaited: bool=True,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    获取群根目录文件列表 action 构造方法
    """
    return BotAction(
        GetGroupRootFilesPack(groupId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetGroupFilesByFolderPack(ActionPack):
    """
    获取群子目录文件列表 action 信息构造类
    """
    def __init__(
        self,
        groupId: int,
        folderId: str
    ) -> None:
        super().__init__()
        self.type = 'get_group_files_by_folder'
        self.params = {
            'group_id': groupId,
            'folder_id': folderId
        }

def get_group_files_byfolder_action(
    groupId: int,
    folderId: str,
    respWaited: bool=True,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    获取群子目录文件列表 action 构造方法
    """
    return BotAction(
        GetGroupFilesByFolderPack(groupId, folderId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class CreateGroupFolderPack(ActionPack):
    """
    创建群文件夹 action 信息构造类
    """
    def __init__(
        self,
        groupId: int,
        folderName: str
    ) -> None:
        super().__init__()
        self.type = 'create_group_file_folder'
        self.params = {
            'group_id': groupId,
            'name': folderName,
            'parent_id': '/'
        }

def create_group_folder_action(
    groupId: int,
    folderName: str,
    respWaited: bool=False,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    创建群文件夹 action 构造方法。注意：只能在根目录创建文件夹
    """
    return BotAction(
        CreateGroupFolderPack(groupId, folderName),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class DeleteGroupFolderPack(ActionPack):
    """
    删除群文件夹 action 信息构造类
    """
    def __init__(
        self,
        groupId: int,
        folderId: str
    ) -> None:
        super().__init__()
        self.type = 'delete_group_folder'
        self.params = {
            'group_id': groupId,
            'folder_id': folderId
        }

def delete_group_folder_action(
    groupId: int,
    folderId: str,
    respWaited: bool=False,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    删除群文件夹 action 构造方法。
    """
    return BotAction(
        DeleteGroupFolderPack(groupId, folderId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class DeleteGroupFilePack(ActionPack):
    """
    删除群文件 action 信息构造类
    """
    def __init__(
        self,
        groupId: int,
        fileId: str,
        fileTypeId: int
    ) -> None:
        super().__init__()
        self.type = 'delete_group_file'
        self.params = {
            'group_id': groupId,
            'file_id': fileId,
            'busid': fileTypeId
        }

def delete_group_file_action(
    groupId: int,
    fileId: str,
    fileTypeId: int,
    respWaited: bool=False,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    删除群文件 action 构造方法。文件相关信息通过 `get_group_root_files_action()` 或
    `get_group_files_action` 的响应获得
    """
    return BotAction(
        DeleteGroupFilePack(groupId, fileId, fileTypeId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetGroupFileUrlPack(ActionPack):
    """
    获取群文件资源链接 action 信息构造类
    """
    def __init__(
        self,
        groupId: int,
        fileId: str,
        fileTypeId: int
    ) -> None:
        super().__init__()
        self.type = 'get_group_file_url'
        self.params = {
            'group_id': groupId,
            'file_id': fileId,
            'busid': fileTypeId
        }

def get_group_file_url_action(
    groupId: int,
    fileId: str,
    fileTypeId: int,
    respWaited: bool=True,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    获取群文件资源链接 action 构造方法。文件相关信息通过 `get_group_root_files_action()` 或
    `get_group_files_action` 的响应获得
    """
    return BotAction(
        GetGroupFileUrlPack(groupId, fileId, fileTypeId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetCqStatusPack(ActionPack):
    """
    获取 go-cqhttp 状态 action 信息构造类
    """
    def __init__(self) -> None:
        super().__init__()
        self.type = 'get_status'
        self.params = {}

def get_cq_status_action(
    respWaited: bool=True,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    获取 go-cqhttp 状态 action 构造方法
    """
    return BotAction(
        GetCqStatusPack(),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetAtAllRemainPack(ActionPack):
    """
    获取群 @全体成员 剩余次数 action 信息构造类
    """
    def __init__(
        self,
        groupId: int
    ) -> None:
        super().__init__()
        self.type = 'get_group_at_all_remain'
        self.params = {
            'group_id': groupId
        }

def get_atall_remain_action(
    groupId: int,
    respWaited: bool=True,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    获取群 @全体成员 剩余次数 action 构造方法
    """
    return BotAction(
        GetAtAllRemainPack(groupId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class QuickHandlePack(ActionPack):
    """
    事件快速操作 action 信息构造类
    """
    def __init__(
        self,
        contextEvent: BotEvent,
        operation: dict
    ) -> None:
        super().__init__()
        self.type = '.handle_quick_operation'
        self.params = {
            'context': contextEvent.raw,
            'operation': operation
        }

def quick_handle_action(
    contextEvent: BotEvent,
    operation: dict,
    respWaited: bool=False,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    事件快速操作 action 构造方法
    """
    return BotAction(
        QuickHandlePack(contextEvent, operation),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class SetGroupNoticePack(ActionPack):
    """
    发送群公告 action 信息构造类
    """
    def __init__(
        self,
        groupId: int,
        content: str,
        imageUrl: str=None
    ) -> None:
        super().__init__()
        self.type = '_send_group_notice'
        self.params = {
            'group_id': groupId,
            'content': content,
        }
        if imageUrl: self.params['image'] = imageUrl

def set_group_notice_action(
    groupId: int,
    content: str,
    imageUrl: str=None,
    respWaited: bool=False,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    发送群公告 action 构造方法。注意 `imageUrl` 只能为本地 url，示例：`file:///C:/users/15742/desktop/123.jpg`
    """
    return BotAction(
        SetGroupNoticePack(groupId, content, imageUrl),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetGroupNoticePack(ActionPack):
    """
    获取群公告 action 信息构造类
    """
    def __init__(
        self,
        groupId: int,
    ) -> None:
        super().__init__()
        self.type = '_get_group_notice'
        self.params = {
            'group_id': groupId,
        }

def get_group_notice_action(
    groupId: int,
    respWaited: bool=True,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    获取群公告 action 构造方法。
    群公告图片有 id，但暂时没有下载的方法
    """
    return BotAction(
        GetGroupNoticePack(groupId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class DownloadFilePack(ActionPack):
    """
    下载文件到缓存目录 action 信息构造类
    """
    def __init__(
        self,
        fileUrl: str,
        useThreadNum: int,
        headers: dict
    ) -> None:
        super().__init__()
        self.type = 'download_file'
        self.params = {
            'url': fileUrl,
            'thread_count': useThreadNum,
            'headers': headers
        }

def download_file_action(
    fileUrl: str,
    useThreadNum: int,
    headers: Union[List, str],
    respWaited: bool=True,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    下载文件到缓存目录 action 构造方法。`headers` 的两种格式：
    ```
    "User-Agent=YOUR_UA[\\r\\n]Referer=https://www.baidu.com"
    ```
    或
    ```python
    [
        "User-Agent=YOUR_UA",
        "Referer=https://www.baidu.com"
    ]
    ```
    """
    return BotAction(
        DownloadFilePack(fileUrl, useThreadNum, headers),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetOnlineClientsPack(ActionPack):
    """
    获取当前账号在线客户端列表 action 信息构造类
    """
    def __init__(
        self,
        noCache: bool
    ) -> None:
        super().__init__()
        self.type = 'get_online_clients'
        self.params = {
            'no_cache': noCache
        }

def get_online_clients_action(
    noCache: bool,
    respWaited: bool=True,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    获取当前账号在线客户端列表 action 构造方法
    """
    return BotAction(
        GetOnlineClientsPack(noCache),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetGroupMsgHistoryPack(ActionPack):
    """
    获取群消息历史记录 action 信息构造类
    """
    def __init__(
        self,
        msgSeq: int,
        groupId: int
    ) -> None:
        super().__init__()
        self.type = 'get_group_msg_history'
        self.params = {
            'message_seq': msgSeq,
            'group_id': groupId
        }

def get_group_msg_history_action(
    msgSeq: int,
    groupId: int,
    respWaited: bool=True,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    获取群消息历史记录 action 构造方法
    """
    return BotAction(
        GetGroupMsgHistoryPack(msgSeq, groupId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class SetGroupEssencePack(ActionPack):
    """
    设置精华消息 action 信息构造类
    """
    def __init__(
        self,
        msgId: int,
        type: Literal['add', 'del']
    ) -> None:
        super().__init__()
        if type == 'add':
            self.type = 'set_essence_msg'
        else:
            self.type = 'delete_essence_msg'
        self.params = {
            'message_id': msgId
        }

def set_group_essence_action(
    msgId: int,
    type: Literal['add', 'del'],
    respWaited: bool=False,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    设置精华消息 action 构造方法
    """
    return BotAction(
        SetGroupEssencePack(msgId, type),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetGroupEssenceListPack(ActionPack):
    """
    获取精华消息列表 action 信息构造类
    """
    def __init__(
        self,
        groupId: int
    ) -> None:
        super().__init__()
        self.type = 'get_essence_msg_list'
        self.params = {
            'group_id': groupId
        }

def get_group_essence_list_action(
    groupId: int,
    respWaited: bool=True,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    获取精华消息列表 action 构造方法
    """
    return BotAction(
        GetGroupEssenceListPack(groupId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetModelShowPack(ActionPack):
    """
    获取在线机型 action 信息构造类
    """
    def __init__(
        self,
        model: str
    ) -> None:
        super().__init__()
        self.type = '_get_model_show'
        self.params = {
            'model': model
        }

def get_model_show_action(
    model: str,
    respWaited: bool=True,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    获取在线机型 action 构造方法
    """
    return BotAction(
        GetModelShowPack(model),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class SetModelShowPack(ActionPack):
    """
    设置在线机型 action 信息构造类
    """
    def __init__(
        self,
        model: str,
        modelShow: str
    ) -> None:
        super().__init__()
        self.type = '_set_model_show'
        self.params = {
            'model': model,
            'model_show': modelShow
        }

def set_model_show_action(
    model: str,
    modelShow: str,
    respWaited: bool=False,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    设置在线机型 action 构造方法
    """
    return BotAction(
        SetModelShowPack(model, modelShow),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class DeleteUndirectFriendPack(ActionPack):
    """
    删除单向好友 action 信息构造类
    """
    def __init__(
        self,
        userId: int
    ) -> None:
        super().__init__()
        self.type = 'delete_unidirectional_friend'
        self.params = {
            'user_id': userId
        }

def delete_undirect_friend_action(
    userId: int,
    respWaited: bool=False,
    triggerEvent: BotEvent=None
) -> BotAction:
    """
    删除单向好友 action 构造方法
    """
    return BotAction(
        DeleteUndirectFriendPack(userId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )