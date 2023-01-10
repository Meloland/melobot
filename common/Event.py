import re
import json
import time as t
from .Typing import *


__all__ = [
    'BotEvent', 
    'KernelEvent'
]


class BotEvent:
    """
    Bot 事件类
    """
    def __init__(self, rawEvent: Union[dict, str]) -> None:
        self.raw: dict = rawEvent if isinstance(rawEvent, dict) else json.loads(rawEvent)
        self.time: float
        self.bot_id: int
        self.type: str

        # 响应事件不会有 time、post_type、self_id
        # 内核事件不会有 self_id
        if 'post_type' in self.raw.keys():
            self.time = self.raw['time']
            self.type = self.raw['post_type']
            # 在获取的历史消息记录中，会有 message_sent 类型，为 bot 发送的消息
            if self.raw['post_type'] == 'message_sent':
                self.type = 'message'
        if 'self_id' in self.raw.keys():
            self.bot_id = self.raw['self_id']
        # 响应事件判断
        if 'retcode' in self.raw.keys():
            self.type = 'response'
        # 为方便各种事件类型的判断，所有类型的信息类都初始化。这样可以暴露各种事件判断的方法接口
        # 比如外部进行私聊消息判断，就只需要: BotEvent(e).msg.is_private()
        self.msg: Msg = Msg()
        self.req: Req = Req()
        self.notice: Notice = Notice()
        self.meta: Meta = Meta()
        self.kernel: Kernel = Kernel()
        self.resp: Resp = Resp()

        self.__build()

    def __build(self) -> None:
        """
        根据类型，构建对应类型的信息
        """
        if self.type == 'message':
            self.msg._Msg__build(self.raw)
        elif self.type == 'request':
            self.req._Req__build(self.raw)
        elif self.type == 'notice':
            self.notice._Notice__build(self.raw)
        elif self.type == 'meta_event':
            self.meta._Meta__build(self.raw)
        elif self.type == 'kernel_event':
            self.kernel._Kernel__build(self.raw)
        elif self.type == 'response':
            self.resp._Resp__build(self.raw)
        else:
            raise ValueError(f"预期之外的事件类型：{self.type}")
    
    def is_msg(self) -> bool:
        """是否为消息事件"""
        return self.type == 'message'
    def is_req(self) -> bool:
        """是否为请求事件"""
        return self.type == 'request'
    def is_notice(self) -> bool:
        """是否为通知事件"""
        return self.type == 'notice'
    def is_meta(self) -> bool:
        """是否为元事件"""
        return self.type == 'meta_event'
    def is_kernel(self) -> bool:
        """是否为内核事件"""
        return self.type == 'kernel_event'
    def is_resp(self) -> bool:
        """是否为响应事件"""
        return self.type == 'response'


class KernelEvent(BotEvent):
    """
    内核事件类。
    用于生成内核事件，可以选择携带触发该内核事件的原事件
    """
    def __init__(self, eventType: str, originEvent: Union[dict, BotEvent, str]=None) -> None:
        origin_e = json.loads(originEvent) if isinstance(originEvent, str) else originEvent
        self.__raw_e = {
            'origin_event': origin_e,
            'time': int(t.time()),
            'post_type': 'kernel_event',
            'sub_type': eventType,
        }
        super().__init__(self.__raw_e)


class MsgSenderInfo:
    """
    消息发送者信息类
    """
    def __init__(self, rawEvent: dict, isGroup: bool, isGroupAnonym: bool) -> None:
        self.__rawEvent = rawEvent
        self.__isGroup = isGroup
        self.id: int
        self.nickname: str
        self.sex: str
        self.age: int

        self.group_card: str
        # 总共有四种：owner, admin, member, anonymous
        self.group_role: str
        self.group_title: str
        self.group_area: str
        self.group_level: str

        self.anonym_id: int
        self.anonym_name: str
        # 匿名用户 flag，调用 go-cqhttp 相关 API 时，需要使用
        self.anonym_flag: str

        self.id = rawEvent['sender']['user_id']
        self.nickname = rawEvent['sender']['nickname']
        self.sex = rawEvent['sender']['sex']
        self.age = rawEvent['sender']['age']
        if isGroup:
            if isGroupAnonym:
                self.group_card = ''
                self.group_area = rawEvent['sender']['area']
                self.group_level = rawEvent['sender']['level']
                self.group_role = 'anonymous'
                self.group_title = ''
                self.anonym_id = rawEvent['anonymous']['id']
                self.anonym_name = rawEvent['anonymous']['name']
                self.anonym_flag = rawEvent['anonymous']['flag']
            else:
                self.group_card = rawEvent['sender']['card']
                self.group_area = rawEvent['sender']['area']
                self.group_level = rawEvent['sender']['level']
                self.group_role = rawEvent['sender']['role']
                self.group_title = rawEvent['sender']['title']


    def is_group_owner(self) -> bool:
        """判断是否为群主，若不是或不是群类型消息，返回 False"""
        if not self.__isGroup: return False
        return self.group_role == 'owner'

    def is_group_admin(self) -> bool:
        """判断是否为群管理（包含群主），若不是或不是群类型消息，返回 False"""
        if not self.__isGroup: return False
        return self.group_role == 'admin' or self.group_role == 'owner'

    def only_group_member(self) -> bool:
        """判断是否只是群员（注意只是群员，不包括群主、管理和匿名），若不是或不是群类型消息，返回 False"""
        if not self.__isGroup: return False
        return self.group_role == 'member'

    def is_anonym_member(self) -> bool:
        """判断是否是群匿名，若不是或不是群类型消息，返回 False"""
        if not self.__isGroup: return False
        return self.group_role == 'anonymous'

    def is_bot(self) -> bool:
        """判断消息是否是bot自己发送的"""
        return self.id == self.__rawEvent['self_id']


TEMP_SRC_MAP = {
    0: '群聊', 
    1: 'QQ咨询', 
    2: '查找', 
    3: 'QQ电影', 
    4: '热聊', 
    6: '验证消息', 
    7: '多人聊天', 
    8: '约会', 
    9: '通讯录'
}


class Msg:
    """
    消息信息类
    """
    def __init__(self) -> None:
        self.id: int
        self.sender: MsgSenderInfo
        self.group_id: int
        # 使用 CQ 码编码非文本消息段
        self.raw_content: str
        # array 格式表示所有类型消息段
        self.content: dict
        # 消息中所有文本消息段的合并字符串
        self.text: str
        self.font: int
        self.temp_src: str

    def __build(self, rawEvent: dict) -> None:
        """
        外部确认为该类型事件时，调用此方法。
        """
        self.__rawEvent = rawEvent
        self.__cq_face_regex = re.compile(r'\[CQ:face,id=(\d+?)\]')
        self.__cq_regex = re.compile(r'\[CQ:.*?\]')
        self.id = rawEvent['message_id']
        self.raw_content = rawEvent['raw_message']
        self.content = rawEvent['message']
        self.font = rawEvent['font']
        self.text = self.__get_text()

        # 初始化为 None，方便外部取值判断
        self.temp_src = None
        if 'temp_source' in rawEvent.keys():
            self.temp_src = TEMP_SRC_MAP[rawEvent['temp_source']]
        self.sender = MsgSenderInfo(
            rawEvent=rawEvent,
            isGroup=self.is_group(),
            isGroupAnonym=self.is_group_anonym()
        )
        # 初始化为 None，方便外部取值判断
        self.group_id = None
        if self.is_group():
            self.group_id = rawEvent['group_id']
        
    def __get_text(self) -> bool:
        """
        获取消息中所有文本消息段，返回合并字符串
        """
        def face_encode(matched: re.Match):
            faceId = int(matched.group(1))
            return f"&faceid={faceId};"
        def face_decode(matched: re.Match):
            return f"[CQ:face,id={matched.group(1)}]"
        
        if isinstance(self.content, str):
            temp_s = self.__cq_face_regex.sub(face_encode, self.content)
            temp_s = self.__cq_regex.sub('', temp_s) \
                    .replace('&amp;', '&')\
                    .replace('&#91;', '[')\
                    .replace('&#93;', ']')\
                    .replace('&#44;', ',')
            return re.sub(r'\&faceid\=(\d+)\;', face_decode, temp_s)
        else:
            temp = []
            for item in self.content:
                if item['type'] == 'text':
                    temp.append(item['data']['text'])
                elif item['type'] == 'face':
                    temp.append(f"[CQ:face,id={item['data']['id']}]")
            return ''.join(temp)

    def __is_msg(self) -> bool:
        """是否为该类型事件"""
        return False if not hasattr(self, '_Msg__rawEvent') else True

    def is_private(self) -> bool:
        """是否为私聊消息（注意群临时会话属于该类别）"""
        if not self.__is_msg(): return False
        return self.__rawEvent['message_type'] == 'private'

    def is_friend(self) -> bool:
        """是否为好友消息"""
        if not self.__is_msg(): return False
        return self.__rawEvent['message_type'] == 'private' and \
            self.__rawEvent['sub_type'] == 'friend'

    def is_group(self) -> bool:
        """是否为群消息（正常群消息、群匿名消息、群自身消息、群系统消息属于该类型）"""
        if not self.__is_msg(): return False
        return self.__rawEvent['message_type'] == 'group'

    def is_group_normal(self) -> bool:
        """是否为正常群消息"""
        if not self.__is_msg(): return False
        return self.__rawEvent['message_type'] == 'group' and \
            self.__rawEvent['sub_type'] == 'normal'

    def is_group_anonym(self) -> bool:
        """是否为匿名群消息"""
        if not self.__is_msg(): return False
        return self.__rawEvent['message_type'] == 'group' and \
            self.__rawEvent['sub_type'] == 'anonymous'

    def is_group_self(self) -> bool:
        """是否为群自身消息（即 bot 自己群中发的消息）"""
        if not self.__is_msg(): return False
        return self.__rawEvent['message_type'] == 'group' and \
            self.__rawEvent['sub_type'] == 'group_self'

    def is_group_temp(self) -> bool:
        """是否为群临时会话（属于私聊的一种）"""
        if not self.__is_msg(): return False
        return self.__rawEvent['message_type'] == 'private' and \
            self.__rawEvent['sub_type'] == 'group'

    def is_temp(self) -> bool:
        """是否为临时会话（属于私聊的一种）"""
        if not self.__is_msg(): return False
        return 'temp_source' in self.__rawEvent.keys()

    def is_group_notice(self) -> bool:
        """是否为群系统消息"""
        if not self.__is_msg(): return False
        return self.__rawEvent['message_type'] == 'group' and \
            self.__rawEvent['sub_type'] == 'notice'


class Req:
    """
    请求信息类
    """
    def __init__(self) -> None:
        self.user_id: int
        self.group_id: int
        # 此处为加群或加好友的验证消息
        self.add_comment: str
        # 请求 flag，调用相关 go-cqhttp API 时，需要使用
        self.add_flag: str
        # 当为加群请求时，类型有：add, invite（加群请求和邀请 bot 入群）
        self.add_group_type: str

    def __build(self, rawEvent: dict) -> None:
        """
        外部确认为该类型事件时，调用此方法。
        """
        self.__rawEvent = rawEvent

        if self.is_friend_req():
            self.user_id = rawEvent['user_id']
            self.add_comment = rawEvent['comment']
            self.add_flag = rawEvent['flag']
        elif self.is_group_req():
            self.add_group_type = rawEvent['sub_type']
            self.user_id = rawEvent['user_id']
            self.group_id = rawEvent['group_id']
            self.add_comment = rawEvent['comment']
            self.add_flag = rawEvent['flag']


    def __is_req(self) -> bool:
        """是否为该类型事件"""
        return False if not hasattr(self, '_Req__rawEvent') else True

    def is_friend_req(self) -> bool:
        """是否为好友请求"""
        if not self.__is_req(): return False
        return self.__rawEvent['request_type'] == 'friend'

    def is_group_req(self) -> bool:
        """是否为群请求"""
        if not self.__is_req(): return False
        return self.__rawEvent['request_type'] == 'group'


class NoticeFileInfo:
    """
    通知中文件信息类
    """
    def __init__(self, rawEvent: dict, isGroup: bool) -> None:
        self.id: str
        self.name: str
        self.size: int
        self.busid: int
        self.url: str

        self.name = rawEvent['file']['name']
        self.size = rawEvent['file']['size']
        if isGroup:
            self.id = rawEvent['file']['id']
            self.busid = rawEvent['file']['busid']
        else:
            self.url = rawEvent['file']['url']


class NoticeClientInfo:
    """
    通知中客户端信息类
    """
    def __init__(self, rawEvent: dict) -> None:
        self.online = rawEvent['online']
        self.id = rawEvent['client']['app_id']
        self.name = rawEvent['client']['device_name']
        self.kind = rawEvent['client']['device_kind']


class Notice:
    """
    通知信息类
    """
    def __init__(self) -> None:
        # 通知作用者或主体方的 id，如被禁言的一方
        self.user_id: int
        # 通知若发生在群中，群 id
        self.group_id: int
        # 通知发起者或操作方的 id，如禁言别人的管理员
        self.operator_id: int
        # 通知涉及消息时，消息 id
        self.msg_id: int
        # 若为入群通知，类型有：approve, invite（管理员同意和管理员邀请）
        self.join_group_type: str
        # 若为退群通知，类型有：leave, kick, kick_me
        self.leave_group_type: str
        # 若为群管理员变动通知，类型有：set, unset
        self.admin_change_type: str
        # 若为文件上传通知，此处为 通知文件信息对象
        self.file: NoticeFileInfo
        # 若为群禁言通知，类型有：ban, lift_ban
        self.group_ban_type: str
        # 若为禁言通知，禁言时长
        self.ban_time: int
        # 若为群荣誉变更通知，类型有：talkactive, performer, emotion
        self.honor_change_type: str
        # 若为群头衔变更通知，新头衔
        self.new_title: str
        # 若为群名片更新事件，旧名片和新名片；注意名片为空时，对应属性为空字符串
        self.old_card: str
        self.new_card: str
        # 若为客户端在线状态变更事件，此处为 通知客户端信息对象
        self.client: NoticeClientInfo
        # 若为精华消息变更事件，类型有：add, delete
        self.essence_change_type: str

    def __build(self, rawEvent: dict=None) -> None:
        """
        外部确认为该类型事件时，调用此方法。
        """
        self.__rawEvent = rawEvent
        
        if self.is_friend_recall():
            self.user_id = rawEvent['user_id']
            self.msg_id = rawEvent['message_id']
        elif self.is_group_recall():
            self.user_id = rawEvent['user_id']
            self.group_id = rawEvent['group_id']
            self.operator_id = rawEvent['operator_id']
            self.msg_id = rawEvent['message_id']
        elif self.is_group_increase():
            self.join_group_type = rawEvent['sub_type']
            self.user_id = rawEvent['user_id']
            self.group_id = rawEvent['group_id']
            self.operator_id = rawEvent['operator_id']
        elif self.is_group_decrease():
            self.leave_group_type = rawEvent['sub_type']
            self.user_id = rawEvent['user_id']
            self.group_id = rawEvent['group_id']
            self.operator_id = rawEvent['operator_id']
        elif self.is_group_admin():
            self.admin_change_type = rawEvent['sub_type']
            self.user_id = rawEvent['user_id']
            self.group_id = rawEvent['group_id']
        elif self.is_group_upload():
            self.user_id = rawEvent['user_id']
            self.group_id = rawEvent['group_id']
            self.file = NoticeFileInfo(rawEvent, isGroup=True)
        elif self.is_group_ban():
            self.user_id = rawEvent['user_id']
            self.group_id = rawEvent['group_id']
            self.operator_id = rawEvent['operator_id']
            self.group_ban_type = rawEvent['sub_type']
            self.ban_time = rawEvent['duration']
        elif self.is_friend_add():
            self.user_id = rawEvent['user_id']
        elif self.is_poke():
            self.user_id = rawEvent['target_id']
            self.operator_id = rawEvent['user_id']
            if 'group_id' in rawEvent.keys():
                self.group_id = rawEvent['group_id']
        elif self.is_lucky_king():
            self.user_id = rawEvent['target_id']
            self.group_id = rawEvent['group_id']
            self.operator_id = rawEvent['user_id']
        elif self.is_honor():
            self.honor_change_type = rawEvent['honor_type']
            self.user_id = rawEvent['user_id']
            self.group_id = rawEvent['group_id']
        elif self.is_title():
            self.new_title = rawEvent['title']
            self.user_id = rawEvent['user_id']
            self.group_id = rawEvent['group_id']
        elif self.is_group_card():
            self.old_card = rawEvent['card_old']
            self.new_card = rawEvent['card_new']
            self.user_id = rawEvent['user_id']
            self.group_id = rawEvent['group_id']
        elif self.is_offline_file():
            self.user_id = rawEvent['user_id']
            self.file = NoticeFileInfo(rawEvent, isGroup=False)
        elif self.is_client_status():
            self.client = NoticeClientInfo(rawEvent)
        elif self.is_essence():
            self.essence_change_type = rawEvent['sub_type']
            self.user_id = rawEvent['sender_id']
            self.group_id = rawEvent['group_id']
            self.operator_id = rawEvent['operator_id']
            self.msg_id = rawEvent['message_id']


    def __is_notice(self) -> bool:
        """是否为该类型事件"""
        return False if not hasattr(self, '_Notice__rawEvent') else True

    def is_group_upload(self) -> bool:
        """是否为群文件上传事件"""
        if not self.__is_notice(): return False
        return self.__rawEvent['notice_type'] == 'group_upload'

    def is_group_admin(self) -> bool:
        """是否为群管理员变更事件"""
        if not self.__is_notice(): return False
        return self.__rawEvent['notice_type'] == 'group_admin'

    def is_group_decrease(self) -> bool:
        """是否为群成员减少事件"""
        if not self.__is_notice(): return False
        return self.__rawEvent['notice_type'] == 'group_decrease'

    def is_group_increase(self) -> bool:
        """是否为群成员增加事件"""
        if not self.__is_notice(): return False
        return self.__rawEvent['notice_type'] == 'group_increase'

    def is_group_ban(self) -> bool:
        """是否为群成员禁言事件"""
        if not self.__is_notice(): return False
        return self.__rawEvent['notice_type'] == 'group_ban'

    def is_friend_add(self) -> bool:
        """是否为好友添加事件"""
        if not self.__is_notice(): return False
        return self.__rawEvent['notice_type'] == 'friend_add'

    def is_group_recall(self) -> bool:
        """是否为群消息撤回事件"""
        if not self.__is_notice(): return False
        return self.__rawEvent['notice_type'] == 'group_recall'

    def is_friend_recall(self) -> bool:
        """是否为好友消息撤回事件"""
        if not self.__is_notice(): return False
        return self.__rawEvent['notice_type'] == 'friend_recall'

    def is_group_card(self) -> bool:
        """是否为群名片变更事件"""
        if not self.__is_notice(): return False
        return self.__rawEvent['notice_type'] == 'group_card'

    def is_offline_file(self) -> bool:
        """是否为离线文件上传事件（即私聊文件上传）"""
        if not self.__is_notice(): return False
        return self.__rawEvent['notice_type'] == 'offline_file'
        
    def is_client_status(self) -> bool:
        """是否为客户端状态变更事件"""
        if not self.__is_notice(): return False
        return self.__rawEvent['notice_type'] == 'client_status'

    def is_essence(self) -> bool:
        """是否为精华消息事件"""
        if not self.__is_notice(): return False
        return self.__rawEvent['notice_type'] == 'essence'
    
    def is_notify(self) -> bool:
        """是否为系统通知事件（包含群荣誉变更、戳一戳、群红包幸运王、群成员头衔变更）"""
        if not self.__is_notice(): return False
        return self.__rawEvent['notice_type'] == 'notify'

    def is_honor(self) -> bool:
        """是否为群荣誉变更事件"""
        if not self.__is_notice(): return False
        return self.__rawEvent['notice_type'] == 'notify' and \
            self.__rawEvent['sub_type'] == 'honor'

    def is_poke(self) -> bool:
        """是否为戳一戳事件"""
        if not self.__is_notice(): return False
        return self.__rawEvent['notice_type'] == 'notify' and \
            self.__rawEvent['sub_type'] == 'poke'

    def is_lucky_king(self) -> bool:
        """是否为群红包幸运王事件"""
        if not self.__is_notice(): return False
        return self.__rawEvent['notice_type'] == 'notify' and \
            self.__rawEvent['sub_type'] == 'lucky_king'

    def is_title(self) -> bool:
        """是否为群成员头衔变更事件"""
        if not self.__is_notice(): return False
        return self.__rawEvent['notice_type'] == 'notify' and \
            self.__rawEvent['sub_type'] == 'title'


class Meta:
    """
    元事件信息类
    """
    def __init__(self) -> None:
        pass

    def __build(self, rawEvent: dict=None) -> None:
        """
        外部确认为该类型事件时，调用此方法。
        """
        self.__rawEvent = rawEvent

    def __is_meta(self) -> bool:
        """是否为该类型事件"""
        return False if not hasattr(self, '_Meta__rawEvent') else True

    def is_lifecycle(self) -> bool:
        """是否为生命周期事件"""
        if not self.__is_meta(): return False
        return self.__rawEvent['meta_event_type'] == 'lifecycle'

    def is_heartbeat(self) -> bool:
        """是否为心跳事件"""
        if not self.__is_meta(): return False
        return self.__rawEvent['meta_event_type'] == 'heartbeat'


class Kernel:
    """
    内核事件信息类
    """
    def __init__(self) -> None:
        self.origin_event: BotEvent

    def __build(self, rawEvent: dict=None) -> None:
        """
        外部确认为该类型事件时，调用此方法。
        """
        # 与其他信息类不同，这里需要取出原事件对象，并转化为 BotEvent
        self.__rawEvent = rawEvent
        if rawEvent['origin_event'] is None or isinstance(rawEvent['origin_event'], BotEvent):
            self.origin_event = rawEvent['origin_event']
        else:
            self.origin_event = BotEvent(rawEvent['origin_event'])

    def __is_kernel(self) -> None:
        """是否为该类型事件"""
        return False if not hasattr(self, '_Kernel__rawEvent') else True

    def is_queue_full(self) -> bool:
        """是否为队列满事件"""
        if not self.__is_kernel(): return False
        return self.__rawEvent['sub_type'] == 'eq_full'


class Resp:
    """
    响应事件信息类。
    具体的响应数据处理不由该类负责，应该由注册的响应事件处理方法负责
    """
    def __init__(self) -> None:
        # 响应标识符
        self.id: str = None
        # 状态码
        self.status: int = None
        # 错误
        self.err: str = None
        # 错误提示
        self.err_prompt: str = None
        # 响应数据
        self.data: dict = None

    def __build(self, rawEvent: dict=None) -> None:
        """
        外部确认为该类型事件时，调用此方法。
        """
        self.__rawEvent = rawEvent
        if rawEvent['retcode'] == 0: self.status = 200
        elif rawEvent['retcode'] == 1: self.status = 202
        else: 
            self.status = 500
            self.err = rawEvent['msg']
            self.err_prompt = rawEvent['wording']
        if 'echo' in rawEvent.keys(): self.id = rawEvent['echo']
        if 'data' in rawEvent.keys(): self.data = rawEvent['data']

    def __is_resp(self) -> bool:
        """是否为该类型事件"""
        return False if not hasattr(self, '_Resp__rawEvent') else True

    def is_ok(self) -> Union[bool, None]:
        """
        判断是否为成功响应
        （注意由于响应事件一般失败、成功都要处理，此处若不是响应事件，则返回 None，而不是 False）
        """
        if not self.__is_resp(): return None
        return self.status == 200

    def is_processing(self) -> Union[bool, None]:
        """
        判断响应是否在被异步处理，即未完成但在处理中
        （注意由于响应事件一般失败、成功都要处理，此处若不是响应事件，则返回 None，而不是 False）
        """
        if not self.__is_resp(): return None
        return self.status == 202

    def is_failed(self) -> Union[bool, None]:
        """
        判断是否为失败响应
        （注意由于响应事件一般失败、成功都要处理，此处若不是响应事件，则返回 None，而不是 False）
        """
        if not self.__is_resp(): return None
        return self.status == 500
