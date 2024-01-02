import json
from abc import ABC
from copy import deepcopy

from ..interface.exceptions import *
from ..interface.typing import *
from .base import ID_WORKER
from .event import *

__all__ = (
    'BotAction', 

    # 消息构造方法
    'text_msg', 
    'face_msg', 
    'audio_msg', 
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
    'cq_format',
    
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
)


def cq_escape(text: str) -> str:
    """
    cq 码特殊字符转义
    """
    return text.replace('&', '&amp;')\
                .replace('[', '&#91;')\
                .replace(']', '&#93;')\
                .replace(',', '&#44;')


def cq_anti_escape(text: str) -> str:
    """
    cq 码特殊字符逆转义
    """
    return text.replace('&amp;', '&')\
                .replace('&#91;', '[')\
                .replace('&#93;', ']')\
                .replace('&#44;', ',')


def cq_format(action: "BotAction") -> "BotAction":
    """
    转化 action 携带的 message 字段转为 cq 字符串格式，并返回新的 action。
    支持的 action 类型有：msg_action 和 forward_action
    """
    def _format_msg_action(action: "BotAction") -> None:
        cq_str_list = []
        for item in action.params['message']:
            if item['type'] != 'text':
                string = f"[CQ:{item['type']}," + \
                ','.join([
                    f"{k}={item['data'][k]}"
                    for k in item['data'].keys()
                ]) + \
                ']'
                cq_str_list.append(string)
            else:
                cq_str_list.append(item['data']['text'])
        action.params['message'] = ''.join(cq_str_list)
    
    def _format_forward_action(action: "BotAction") -> None:
        for item in action.params['messages']:
            if 'id' in item['data'].keys():
                continue
            
            cq_str_list = []
            for msg in item['data']['content']:
                if msg['type'] != 'text':
                    string = f"[CQ:{msg['type']}," + \
                    ','.join([
                        f"{k}={msg['data'][k]}"
                        for k in msg['data'].keys()
                    ]) + \
                    ']'
                    cq_str_list.append(string)
                else:
                    cq_str_list.append(msg['data']['text'])
            item['data']['content'] = ''.join(cq_str_list)
    
    _action = deepcopy(action)
    if _action.type == 'send_msg':
        _format_msg_action(_action)
    elif _action.type in ('send_private_forward_msg', 'send_group_forward_msg'):
        _format_forward_action(_action)
    else:
        raise BotTypeError("传入的 action 因类型不匹配，不可被 cq 序列化")

    return _action



def text_msg(
    text: str,
) -> Msg:
    """
    普通文本消息
    """
    return {
        "type": "text",
        "data": {
            "text": text
        }
    }


def face_msg(
    icon_id: int, 
) -> Msg:
    """
    QQ 表情
    """
    return {
        "type": "face",
        "data": {
            "id": f"{icon_id}"
        }
    }


def audio_msg(
    url: str, 
    timeout: int=None, 
    magic: bool=False, 
) -> Msg:
    """
    语音消息
    """
    base =  {
        "type": "record",
        "data": {
            "file": url,
        }
    }
    if magic: base['data']['magic'] = 1
    if timeout: base['data']['timeout'] = str(timeout)
    return base


def at_msg(
    qqId:Union[int ,Literal['all']], 
    notInName: str=None, 
) -> Msg:
    """
    at 消息。
    at 所有人时，`qqId` 传 "all"
    """
    base = {
        "type": "at",
        "data": {
            "qq": str(qqId),
        }
    }
    if notInName: base['data']['name'] = notInName
    return base


def share_msg(
    url: str, 
    title: str, 
    content: str=None, 
    image: str=None, 
) -> Msg:
    """
    链接分享卡片消息。
    `content` 为描述语
    """
    base = {
        "type": "share",
        "data": {
            "url": url,
            "title": title,
        }
    }
    if content: base['data']['content'] = content
    if image: base['data']['image'] = image
    return base


def music_msg(
    platType: Literal["qq", "163", "xm"],
    songId: str, 
) -> Msg:
    """
    音乐分享卡片消息（专有平台）
    """
    return {
        "type": "music",
        "data": {
            "type": platType,
            "id": songId
        }
    }


def custom_music_msg(
    url: str, 
    audio: str, 
    title: str, 
    content: str=None, 
    image: str=None, 
) -> Msg:
    """
    自定义音乐分享卡片。
    `url` 为主页或网站起始页
    """
    base = {
        "type": "music",
        "data": {
            "type": "custom",
            "url": url,
            "audio": audio,
            "title": title,
        }
    }
    if content: base['data']['content'] = content
    if image: base['data']['image'] = image
    return base


def image_msg(
    url: str, 
    picType: Literal["flash", "show"]=None, 
    subType: Literal[0, 1]=None, 
    useCache: Literal[0, 1]=1,
) -> Msg:
    """
    图片消息。
    `url`: 图片 url。可以为本地路径，如：`file:///C:/users/15742/desktop/QQ图片20230108225606.jpg`；也可以为网络 url；还可以为 image id。
    `picType`: flash 为闪照，show 为秀图，不填为普通图片。
    `subType`: 只出现在群聊，0 为正常图片，1 为表情包
    """
    base = {
        "type": "image",
        "data": {
            "file": url,
        }
    }
    if picType: base['data']['type'] = picType
    if subType: base['data']['subType'] = subType
    if useCache: base['data']['cache'] = useCache
    return base


def reply_msg(
    messageId: int, 
) -> Msg:
    """
    回复消息
    """
    return {
        "type": "reply",
        "data": {
            "id": messageId,
        }
    }


def poke_msg(
    qqId: int, 
) -> Msg:
    """
    戳一戳消息
    """
    return {
        "type": "poke",
        "data": {
            "qq": qqId,
        }
    }


def tts_msg(
    text: str, 
) -> Msg:
    """
    腾讯自带 tts 语音消息
    """
    return {
        "type": "tts",
        "data": {
            "text": text,
        }
    }


def custom_msg_node(
    content: Union[str, Msg, MsgSegment], 
    sendName:str, 
    sendId: int,
    seq: str=None,
) -> MsgNode:
    """
    自定义消息节点构造方法。转化字符串、消息、消息段为消息节点
    """
    if isinstance(content, str):
        msgs = text_msg(content)
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


class ActionPacker(ABC): 
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
        package: ActionPacker,
        respWaited: bool=False, 
        triggerEvent: BotEvent=None
    ) -> None:
        # 只有 action 对应的响应需要被等待单独处理时，才会生成 id
        self.resp_id: Union[str, None] = str(ID_WORKER.get_id()) if respWaited else None
        self.type: str = package.type
        self.params: dict = package.params
        self.trigger: Union[BotEvent, None] = triggerEvent

    def extract(self) -> dict:
        """
        从对象提取标准 cq action dict
        """
        obj = {
            'action': self.type,
            "params": self.params,
        }
        if self.resp_id: obj['echo'] = self.resp_id
        return obj

    def flatten(self) -> str:
        """
        将对象序列化为标准 cq action json 字符串，一般供连接器使用
        """
        return json.dumps(self.extract(), ensure_ascii=False)


class MsgPacker(ActionPacker):
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
    content: Union[str, Msg, MsgSegment],
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
        msgs = text_msg(content)
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
        raise BotTypeError("content 参数类型不正确，无法封装")
    return BotAction(
        MsgPacker(
            msgs, isPrivate, userId, groupId
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class ForwardMsgPacker(ActionPacker):
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
                'messages': msgs,
                'auto_escape': True
            }
        else:
            self.type = 'send_group_forward_msg'
            self.params = {
                'group_id': groupId,
                'messages': msgs,
                'auto_escape': True
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
        ForwardMsgPacker(
            msgNodes, isPrivate, userId, groupId
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class MsgDelPacker(ActionPacker):
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
        MsgDelPacker(msgId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetMsgPacker(ActionPacker):
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
        GetMsgPacker(msgId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class getForwardPacker(ActionPacker):
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
        getForwardPacker(forwardId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class getImagePacker(ActionPacker):
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
        getImagePacker(fileName),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class MarkMsgReadPacker(ActionPacker):
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
        MarkMsgReadPacker(msgId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GroupKickPacker(ActionPacker):
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
        GroupKickPacker(
            groupId, userId, laterReject
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GroupBanPacker(ActionPacker):
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
        GroupBanPacker(
            groupId, userId, duration
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GroupAnonymBanPacker(ActionPacker):
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
        GroupAnonymBanPacker(
            groupId, anonymFlag, duration
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GroupWholeBanPacker(ActionPacker):
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
        GroupWholeBanPacker(
            groupId, enable
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class SetGroupAdminPacker(ActionPacker):
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
        SetGroupAdminPacker(
            groupId, userId, enable
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class SetGroupCardPacker(ActionPacker):
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
        SetGroupCardPacker(groupId, userId, card),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class SetGroupNamePacker(ActionPacker):
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
        SetGroupNamePacker(groupId, name),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GroupLeavePacker(ActionPacker):
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
        GroupLeavePacker(
            groupId, isDismiss
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class SetGroupTitlePacker(ActionPacker):
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
        SetGroupTitlePacker(
            groupId, userId, title, duration
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GroupSignPacker(ActionPacker):
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
        GroupSignPacker(groupId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class SetFriendAddPacker(ActionPacker):
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
        SetFriendAddPacker(
            addFlag, approve, remark
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )
        

class SetGroupAddPacker(ActionPacker):
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
        SetGroupAddPacker(
            addFlag, addType, approve, rejectReason
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetLoginInfoPacker(ActionPacker):
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
        GetLoginInfoPacker(),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class SetLoginProfilePacker(ActionPacker):
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
        SetLoginProfilePacker(
            nickname, company, email, college, personalNote
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )

        
class GetStrangerInfoPacker(ActionPacker):
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
        GetStrangerInfoPacker(
            userId, noCache
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetFriendListPacker(ActionPacker):
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
        GetFriendListPacker(),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetUndirectFriendPacker(ActionPacker):
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
        GetUndirectFriendPacker(),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class DeleteFriendPacker(ActionPacker):
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
        DeleteFriendPacker(userId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetGroupInfoPacker(ActionPacker):
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
        GetGroupInfoPacker(
            groupId, noCache
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetGroupListPacker(ActionPacker):
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
        GetGroupListPacker(),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetGroupMemberInfoPacker(ActionPacker):
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
        GetGroupMemberInfoPacker(
            groupId, userId, noCache
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetGroupMemberListPacker(ActionPacker):
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
        GetGroupMemberListPacker(
            groupId, noCache
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetGroupHonorPacker(ActionPacker):
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
        GetGroupHonorPacker(
            groupId, type
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class CheckSendImagePacker(ActionPacker):
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
        CheckSendImagePacker(),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class CheckSendRecordPacker(ActionPacker):
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
        CheckSendRecordPacker(),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetCqVersionPacker(ActionPacker):
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
        GetCqVersionPacker(),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class SetGroupPortraitPacker(ActionPacker):
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
        SetGroupPortraitPacker(
            groupId, file, cache
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class OcrPacker(ActionPacker):
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
        OcrPacker(image),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetGroupSysMsgPacker(ActionPacker):
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
        GetGroupSysMsgPacker(),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class UploadFilePacker(ActionPacker):
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
        UploadFilePacker(
            isPrivate, file, sendFileName, userId, groupId, groupFolderId
        ),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetGroupFileSysInfoPacker(ActionPacker):
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
        GetGroupFileSysInfoPacker(groupId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetGroupRootFilesPacker(ActionPacker):
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
        GetGroupRootFilesPacker(groupId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetGroupFilesByFolderPacker(ActionPacker):
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
        GetGroupFilesByFolderPacker(groupId, folderId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class CreateGroupFolderPacker(ActionPacker):
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
        CreateGroupFolderPacker(groupId, folderName),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class DeleteGroupFolderPacker(ActionPacker):
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
        DeleteGroupFolderPacker(groupId, folderId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class DeleteGroupFilePacker(ActionPacker):
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
        DeleteGroupFilePacker(groupId, fileId, fileTypeId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetGroupFileUrlPacker(ActionPacker):
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
        GetGroupFileUrlPacker(groupId, fileId, fileTypeId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetCqStatusPacker(ActionPacker):
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
        GetCqStatusPacker(),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetAtAllRemainPacker(ActionPacker):
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
        GetAtAllRemainPacker(groupId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class QuickHandlePacker(ActionPacker):
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
        QuickHandlePacker(contextEvent, operation),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class SetGroupNoticePacker(ActionPacker):
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
        SetGroupNoticePacker(groupId, content, imageUrl),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetGroupNoticePacker(ActionPacker):
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
        GetGroupNoticePacker(groupId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class DownloadFilePacker(ActionPacker):
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
        DownloadFilePacker(fileUrl, useThreadNum, headers),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetOnlineClientsPacker(ActionPacker):
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
        GetOnlineClientsPacker(noCache),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetGroupMsgHistoryPacker(ActionPacker):
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
        GetGroupMsgHistoryPacker(msgSeq, groupId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class SetGroupEssencePacker(ActionPacker):
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
        SetGroupEssencePacker(msgId, type),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetGroupEssenceListPacker(ActionPacker):
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
        GetGroupEssenceListPacker(groupId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class GetModelShowPacker(ActionPacker):
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
        GetModelShowPacker(model),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class SetModelShowPacker(ActionPacker):
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
        SetModelShowPacker(model, modelShow),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )


class DeleteUndirectFriendPacker(ActionPacker):
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
        DeleteUndirectFriendPacker(userId),
        respWaited=respWaited,
        triggerEvent=triggerEvent
    )