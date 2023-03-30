from functools import wraps
from collections import OrderedDict
from .Store import BOT_STORE
from .Event import BotEvent, RespEvent
from .Action import *
from .Typing import *
from .Exceptions import *
import asyncio as aio
import time


__all__ = [
    'BotSession',

    'face_msg', 
    'text_msg', 
    'audio_msg', 
    'at_msg', 
    'share_msg', 
    'music_msg', 
    'custom_music_msg', 
    'image_msg', 
    'reply_msg', 
    'poke_msg', 
    'tts_msg',
    'cq_escape',
    'cq_anti_escape',

    'custom_msg_node',
    'refer_msg_node'
]

audio_msg = record_msg


class BotSession:
    """
    Bot Session 类。禁止直接实例化，必须通过 SessionBuilder 构造。
    所有 event 响应前，需要生成附加的 session 信息，用以判断会话状态
    """
    def __init__(self, sessionsSpace: List["BotSession"]) -> None:
        self.__expires = False
        self.__sessions_space = sessionsSpace
        self.store = {}
        self.crt_time = time.time()
        self.event_records: OrderedDict[BotEvent, int] = OrderedDict()
        # session 活动状态。当一 session 处于活动状态时，应该拒绝再次获取
        self.__activated = False
        self.__responder = BOT_STORE.monitor.responder

    def __add_event(self, event: BotEvent) -> None:
        if event in self.event_records.keys():
            self.event_records[event] += 1
        else:
            self.event_records[event] = 1

    @property
    def event(self) -> Union[BotEvent, None]: 
        try: return next(reversed(self.event_records))
        except IndexError: return "No event attached temporarily"

    def store_get(self, key: object) -> object: return self.store[key]

    def store_add(self, key: object, val: object) -> None: self.store[key] = val

    def store_update(self, store: Dict) -> None: self.store.update(store)
    
    def store_remove(self, key: object) -> None: self.store.pop(key)

    def destory(self) -> None:
        """
        销毁当前 session，即从 session 空间中删除该 session
        """
        if not self.__expires:
            self.__sessions_space.remove(self)
            self.__expires = True

    # 不要更改这个方法下的所有 typing，否则会影响被装饰方法的 typing
    def __action_launch(get_action):
        """
        action 构建方法的装饰器，
        在 action 构建后进行发送，以及完成响应等待
        """
        @wraps(get_action)
        async def wrapper(self: "BotSession", *args, **kwargs):
            action: BotAction = get_action(self, *args, **kwargs)
            if action.respId is None:
                return await self.__responder.throw_action(action)
            else:
                return await self.__responder.wait_action(action)
        return wrapper


    @__action_launch
    def send(
        self, 
        content: Union[str, Msg, MsgSegment], 
        waitResp: bool=False
    ) -> Union[RespEvent, None]:
        """
        在当前 session 上下文下发送消息
        """
        return msg_action(
            content, 
            self.event.msg.is_private(),
            self.event.msg.sender.id,
            self.event.msg.group_id,
            waitResp,
            self.event
        )

    @__action_launch
    def custom_send(
        self,
        content: Union[str, Msg, MsgSegment],
        isPrivate: bool,
        userId: int, 
        groupId: int=None,
        waitResp: bool=False,
    ) -> Union[RespEvent, None]:
        """
        自定义发送消息
        """
        return msg_action(
            content, 
            isPrivate, 
            userId, 
            groupId, 
            waitResp, 
            self.event
        )
    
    @__action_launch
    def send_forward(
        self,
        msgNodes: MsgNodeList,
        waitResp: bool=False
    ) -> Union[RespEvent, None]:
        """
        在当前 session 上下文下发送转发消息
        """
        return forward_msg_action(
            msgNodes,
            self.event.msg.is_private(),
            self.event.msg.sender.id,
            self.event.msg.group_id,
            waitResp,
            self.event
        )
        
    @__action_launch
    def custom_send_forward(
        self,
        msgNodes: MsgNodeList,
        isPrivate: bool,
        userId: int=None, 
        groupId: int=None,
        waitResp: bool=False,
    ) -> Union[RespEvent, None]:
        """
        自定义发送转发消息
        """
        return forward_msg_action(
            msgNodes,
            isPrivate,
            userId,
            groupId,
            waitResp,
            self.event
        )
    
    @__action_launch
    def recall(
        self,
        msgId: int,
        waitResp: bool=False
    ) -> Union[RespEvent, None]:
        """
        撤回消息
        """
        return msg_del_action(
            msgId,
            waitResp,
            self.event
        )
    
    @__action_launch
    def get_msg(
        self,
        msgId: int
    ) -> Union[RespEvent, None]:
        """
        获取消息信息
        """
        return get_msg_action(
            msgId,
            True,
            self.event
        )
    
    @__action_launch
    def get_forward_msg(
        self,
        forwardId: str,
    ) -> Union[RespEvent, None]:
        """
        获取转发消息信息
        """
        return get_forward_msg_action(
            forwardId,
            True,
            self.event
        )
    
    @__action_launch
    def mark_read(
        self,
        msgId: int,
        waitResp: bool=False
    ) -> Union[RespEvent, None]:
        """
        标记为已读
        """
        return mark_msg_read_action(
            msgId,
            waitResp,
            self.event
        )

    
    @__action_launch
    def group_kick(
        self,
        groupId: int,
        userId: int,
        laterReject: bool=False,
        waitResp: bool=False,
    ) -> Union[RespEvent, None]:
        """
        群组踢人
        """
        return group_kick_action(
            groupId,
            userId,
            laterReject,
            waitResp,
            self.event
        )
    
    @__action_launch
    def group_ban(
        self,
        groupId: int,
        userId: int,
        duration: int,
        waitResp: bool=False,
    ) -> Union[RespEvent, None]:
        """
        群组禁言。
        duration 为 0 取消禁言
        """
        return group_ban_action(
            groupId,
            userId,
            duration,
            waitResp,
            self.event
        )
    
    @__action_launch
    def group_ban_anonymous(
        self,
        groupId: int,
        anonymFlag: str,
        duration: int,
        waitResp: bool=False,
    ) -> Union[RespEvent, None]:
        """
        群组匿名禁言。
        无法取消禁言
        """
        return group_anonym_ban_action(
            groupId,
            anonymFlag,
            duration,
            waitResp,
            self.event
        )
        
    @__action_launch
    def group_ban_all(
        self,
        groupId: int,
        enable: bool,
        waitResp: bool=False,
    ) -> Union[RespEvent, None]:
        """
        群组全员禁言
        """
        return group_whole_ban_action(
            groupId,
            enable,
            waitResp,
            self.event
        )
        
    @__action_launch
    def group_leave(
        self,
        groupId: int,
        isDismiss: bool,
        waitResp: bool=False,
    ) -> Union[RespEvent, None]:
        """
        退出群组
        """
        return group_leave_action(
            groupId,
            isDismiss,
            waitResp,
            self.event
        )
    
    @__action_launch
    def group_sign(
        self,
        groupId: int,
        waitResp: bool=False,
    ) -> Union[RespEvent, None]:
        """
        群组打卡
        """
        return group_sign_action(
            groupId,
            waitResp,
            self.event
        )
    
    
    @__action_launch
    def get_group(
        self,
        groupId: int,
        noCache: bool,
    ) -> Union[RespEvent, None]:
        """
        获取群信息
        """
        return get_group_info_action(
            groupId,
            noCache,
            True,
            self.event
        )
    
    @__action_launch
    def get_groups(
        self
    ) -> Union[RespEvent, None]:
        """
        获取 bot 加入的群列表
        """
        return get_group_list_action(
            True,
            self.event
        )
        
    @__action_launch
    def get_group_member(
        self,
        groupId: int,
        userId: int,
        noCache: bool,
    ) -> Union[RespEvent, None]:
        """
        获取群内单独一个群成员信息
        """
        return get_group_member_info_action(
            groupId,
            userId,
            noCache,
            True,
            self.event
        )
    
    @__action_launch
    def get_group_members(
        self,
        groupId: int,
        noCache: bool,
    ) -> Union[RespEvent, None]:
        """
        获取群成员列表
        """
        return get_group_member_list_action(
            groupId,
            noCache,
            True,
            self.event
        )
        
    @__action_launch
    def get_group_honor(
        self,
        groupId: int,
        type: Literal['talkative', 'performer', 'legend', 'strong_newbie', 'emotion', 'all']
    ) -> Union[RespEvent, None]:
        """
        获取群荣誉信息
        """
        return get_group_honor_action(
            groupId,
            type,
            True,
            self.event
        )
        
    @__action_launch
    def get_group_file_sys(
        self,
        groupId: int,
    ) -> Union[RespEvent, None]:
        """
        获取群文件系统信息
        """
        return get_group_filesys_info_action(
            groupId,
            True,
            self.event
        )
    
    @__action_launch
    def get_group_root_files(
        self,
        groupId: int,
    ) -> Union[RespEvent, None]:
        """
        获取群根目录文件列表
        """
        return get_group_root_files_action(
            groupId,
            True,
            self.event
        )
    
    @__action_launch
    def get_group_files_in_folder(
        self,
        groupId: int,
        folderId: str
    ) -> Union[RespEvent, None]:
        """
        获取群子目录文件列表
        """
        return get_group_files_byfolder_action(
            groupId,
            folderId,
            True,
            self.event
        )
        
    @__action_launch
    def get_group_file_url(
        self,
        groupId: int,
        fileId: str,
        fileTypeId: int
    ) -> Union[RespEvent, None]:
        """
        获取群文件资源链接。文件相关信息通过 `get_group_root_files` 或
        `get_group_files` 的响应获得
        """
        return get_group_file_url_action(
            groupId,
            fileId,
            fileTypeId,
            True,
            self.event
        )
    
    @__action_launch
    def get_group_sys_msg(
        self
    ) -> Union[RespEvent, None]:
        """
        获取群系统消息
        """
        return get_group_sys_msg_action(
            True,
            self.event
        )
    
    @__action_launch
    def get_group_notices(
        self,
        groupId: int,
    ) -> Union[RespEvent, None]:
        """
        获取群公告。
        群公告图片有 id，但暂时没有下载的方法
        """
        return get_group_notice_action(
            groupId,
            True,
            self.event
        )
        
    @__action_launch
    def get_group_records(
        self,
        msgSeq: int,
        groupId: int
    ) -> Union[RespEvent, None]:
        """
        获取群消息历史记录
        """
        return get_group_msg_history_action(
            msgSeq,
            groupId,
            True,
            self.event
        )
        
    @__action_launch
    def get_group_essences(
        self,
        groupId: int
    ) -> Union[RespEvent, None]:
        """
        获取精华消息列表
        """
        return get_group_essence_list_action(
            groupId,
            True,
            self.event
        )


    @__action_launch
    def set_group_admin(
        self,
        groupId: int,
        userId: int,
        enable: bool,
        waitResp: bool=False
    ) -> Union[RespEvent, None]:
        """
        设置群管理员
        """
        return set_group_admin_action(
            groupId,
            userId,
            enable,
            waitResp,
            self.event
        )
    
    @__action_launch
    def set_group_card(
        self,
        groupId: int,
        userId: int,
        card: str,
        waitResp: bool=False
    ) -> Union[RespEvent, None]:
        """
        设置群名片
        """
        return set_group_card_action(
            groupId,
            userId,
            card,
            waitResp,
            self.event
        ) 
    
    @__action_launch
    def set_group_name(
        self,
        groupId: int,
        name: str,
        waitResp: bool=False
    ) -> Union[RespEvent, None]:
        """
        设置群名
        """
        return set_group_name_action(
            groupId,
            name,
            waitResp,
            self.event
        ) 
        
    @__action_launch
    def set_group_title(
        self,
        groupId: int,
        userId: int,
        title: str,
        duration: int=-1,
        waitResp: bool=False
    ) -> Union[RespEvent, None]:
        """
        设置群头衔
        """
        return set_group_title_action(
            groupId,
            userId,
            title,
            duration,
            waitResp,
            self.event
        )
        
    @__action_launch
    def process_group_add(
        self,
        addFlag: str,
        addType: Literal['add', 'invite'],
        approve: bool,
        rejectReason: str=None,
        waitResp: bool=False
    ) -> Union[RespEvent, None]:
        """
        处理加群请求
        """
        return set_group_add_action(
            addFlag,
            addType,
            approve,
            rejectReason,
            waitResp,
            self.event
        )
    
    @__action_launch
    def set_group_icon(
        self,
        groupId: int,
        file: str,
        cache: Literal[0, 1]=0,
        waitResp: bool=False
    ) -> Union[RespEvent, None]:
        """
        设置群头像。file 参数接受本地或网络 url 和 base64 编码。
        如本地路径为：`file:///C:/Users/Richard/Pictures/1.png`。
        特别注意：目前此 API 在登录一段时间后会因 cookie 失效而失效
        """
        return set_group_portrait_action(
            groupId,
            file,
            cache,
            waitResp,
            self.event
        )
    
    @__action_launch
    def set_group_notice(
        self,
        groupId: int,
        content: str,
        imageUrl: str=None,
        waitResp: bool=False
    ) -> Union[RespEvent, None]:
        """
        发送群公告。
        注意 `imageUrl` 只能为本地 url，示例：`file:///C:/users/15742/desktop/123.jpg`
        """
        return set_group_notice_action(
            groupId,
            content,
            imageUrl,
            waitResp,
            self.event
        ) 
        
    @__action_launch
    def set_group_essence(
        self,
        msgId: int,
        type: Literal['add', 'del'],
        waitResp: bool=False
    ) -> Union[RespEvent, None]:
        """
        设置群精华消息
        """
        return set_group_essence_action(
            msgId,
            type,
            waitResp,
            self.event
        )
        
    @__action_launch
    def create_group_folder(
        self,
        groupId: int,
        folderName: str,
        waitResp: bool=False
    ) -> Union[RespEvent, None]:
        """
        创建群文件夹。注意：只能在根目录创建文件夹
        """
        return create_group_folder_action(
            groupId,
            folderName,
            waitResp,
            self.event
        )
        
    @__action_launch
    def delete_group_folder(
        self,
        groupId: int,
        folderId: str,
        waitResp: bool=False
    ) -> Union[RespEvent, None]:
        """
        删除群文件夹
        """
        return delete_group_folder_action(
            groupId,
            folderId,
            waitResp,
            self.event
        )
        
    @__action_launch
    def delete_group_file(
        self,
        groupId: int,
        fileId: str,
        fileTypeId: int,
        waitResp: bool=False
    ) -> Union[RespEvent, None]:
        """
        删除群文件。文件相关信息通过 `get_group_root_files` 或
        `get_group_files` 的响应获得
        """
        return delete_group_file_action(
            groupId,
            fileId,
            fileTypeId,
            waitResp,
            self.event
        )


    @__action_launch
    def get_friends(
        self
    ) -> Union[RespEvent, None]:
        """
        获取好友列表
        """
        return get_friend_list_action(
            True,
            self.event
        )
        
    @__action_launch
    def get_undirect_friends(
        self
    ) -> Union[RespEvent, None]:
        """
        获取单向好友列表
        """
        return get_undirect_friend_action(
            True,
            self.event
        )
    
    @__action_launch
    def get_user(
        self,
        userId: int,
        noCache: bool,
    ) -> Union[RespEvent, None]:
        """
        获取用户信息。可以对陌生人或好友使用
        """
        return get_stranger_info_action(
            userId,
            noCache,
            True,
            self.event
        )
        
    @__action_launch
    def process_friend_add(
        self,
        addFlag: str,
        approve: bool,
        remark: str,
        waitResp: bool=False
    ) -> Union[RespEvent, None]:
        """
        处理加好友。注意 remark 目前暂未实现
        """
        return set_friend_add_action(
            addFlag,
            approve,
            remark,
            waitResp,
            self.event
        ) 
    
    @__action_launch
    def delete_friend(
        self,
        userId: int,
        waitResp: bool=False
    ) -> Union[RespEvent, None]:
        """
        删除好友
        """
        return delete_friend_action(
            userId,
            waitResp,
            self.event
        ) 
        
    @__action_launch
    def delete_undirect_friend(
        self,
        userId: int,
        waitResp: bool=False
    ) -> Union[RespEvent, None]:
        """
        删除单向好友
        """
        return delete_undirect_friend_action(
            userId,
            waitResp,
            self.event
        )  
    

    
    @__action_launch
    def get_login_info(
        self,
    ) -> Union[RespEvent, None]:
        """
        获得登录号信息
        """
        return get_login_info_action(
            True,
            self.event
        )
    
    @__action_launch
    def set_login_profile(
        self,
        nickname: str,
        company: str,
        email: str,
        college: str,
        personalNote: str,
        waitResp: bool=False
    ) -> Union[RespEvent, None]:
        """
        设置登录号资料
        """
        return set_login_profile_action(
            nickname,
            company,
            email,
            college,
            personalNote,
            waitResp,
            self.event
        )
    
    @__action_launch
    def check_send_image(
        self
    ) -> Union[RespEvent, None]:
        """
        检查是否可以发送图片
        """
        return check_send_image_action(
            True,
            self.event
        )
        
    @__action_launch
    def check_send_audio(
        self
    ) -> Union[RespEvent, None]:
        """
        检查是否可以发送语音
        """
        return check_send_record_action(
            True,
            self.event
        )
    
    @__action_launch
    def get_cq_status(
        self
    ) -> Union[RespEvent, None]:
        """
        获取 go-cqhttp 状态
        """
        return get_cq_status_action(
            True,
            self.event
        )
    
    @__action_launch
    def get_cq_version(
        self
    ) -> Union[RespEvent, None]:
        """
        获取 go-cqhttp 版本信息
        """
        return get_cq_version_action(
            True,
            self.event
        )
        
    @__action_launch
    def quick_handle(
        self,
        contextEvent: BotEvent,
        operation: dict,
        waitResp: bool=False,
    ) -> Union[RespEvent, None]:
        """
        事件快速操作（该方法下一版本实现，本版本无法使用）
        """
        raise ReferenceError("该方法下一版本实现，本版本无法使用")
        # return quick_handle_action(
        #     contextEvent,
        #     operation,
        #     waitResp,
        #     self.event
        # )
    
    @__action_launch
    def get_image(
        self,
        fileName: str
    ) -> Union[RespEvent, None]:
        """
        获取图片信息
        """
        return get_image_action(
            fileName,
            True,
            self.event
        )
    
    @__action_launch
    def download_file(
        self,
        fileUrl: str,
        useThreadNum: int,
        headers: Union[List, str],
        waitResp: bool=True,
    ) -> Union[RespEvent, None]:
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
        return download_file_action(
            fileUrl,
            useThreadNum,
            headers,
            waitResp,
            self.event
        )
        
    @__action_launch
    def ocr(
        self,
        image: str,
    ) -> Union[RespEvent, None]:
        """
        图片 OCR。image 为图片 ID
        """
        return ocr_action(
            image,
            True,
            self.event
        )
    
    @__action_launch
    def upload_file(
        self,
        isPrivate: bool,
        file: str,
        sendFileName: str,
        userId: int=None,
        groupId: int=None,
        groupFolderId: str=None,
        waitResp: bool=False
    ) -> Union[RespEvent, None]:
        """
        发送文件 action 构造方法。只支持发送本地文件。
        若为群聊文件发送，不提供 folder id，则默认上传到群文件根目录。
        
        示例路径：`C:/users/15742/desktop/QQ图片20230108225606.jpg`。
        
        （若需要发送网络文件，先使用 `download_file` 方法下载网络文件。
        响应后文件会放于 go-cqhttp 缓存文件夹中，可直接在消息段中引用）
        """
        return upload_file_action(
            isPrivate,
            file,
            sendFileName,
            userId,
            groupId,
            groupFolderId,
            waitResp,
            self.event
        )
    
    @__action_launch
    def get_at_all_remain(
        self,
        groupId: int
    ) -> Union[RespEvent, None]:
        """
        获取群 @全体成员 剩余次数
        """
        return get_atall_remain_action(
            groupId,
            True,
            self.event
        )
    
    @__action_launch
    def get_online_clients(
        self,
        noCache: bool,
    ) -> Union[RespEvent, None]:
        """
        获取当前账号在线客户端列表
        """
        return get_online_clients_action(
            noCache,
            True,
            self.event
        )
    
    @__action_launch
    def get_model_show(
        self,
        model: str,
    ) -> Union[RespEvent, None]:
        """
        获取在线机型
        """
        return get_model_show_action(
            model,
            True,
            self.event
        )
    
    @__action_launch
    def set_model_show(
        self,
        model: str,
        modelShow: str
    ) -> Union[RespEvent, None]:
        """
        设置在线机型
        """
        return set_model_show_action(
            model,
            modelShow,
            True,
            self.event
        )


class Reflector:
    """
    通过反射获取值
    """
    @classmethod
    def get(cls, obj: object, attrs: tuple) -> object:
        """
        反射获取
        """
        val = obj
        for attr in attrs: 
            val = getattr(val, attr)
        return val
    
    @classmethod
    def set(cls, obj: object, attrs: tuple, val: object) -> None:
        """
        反射设置
        """
        field = obj
        for attr in attrs[:-1]: 
            field = getattr(field, attr)
        setattr(field, attrs[-1], val)


class SessionManager:
    """
    Bot session 管理类
    """
    async def get_session(
        self, 
        event: BotEvent,
        cmdSessionsSpace: List[BotSession]=None,
        checkAttr: Union[Tuple[str, ...], str]=None,
        checkMethod: Callable[[BotEvent, BotEvent], bool]=None,
        lock: aio.Lock=None
    ) -> Union[BotSession, None]:
        """
        `event`: 附着的 BotEvent
        `store`: 生成 session 的 store
        `uniqueAttr`: 用于校验是否为同一 session 的 BotEvent 属性。当使用 Tuple 传参时，有以下特征：
        ```python
        # uniqueAttr = ('a', 'b', 'c') 时，用于校验的属性是：
        event.a.b.c
        ```
        `UniqueCheck`: 绑定了 check_method_bind 装饰器的自定义校验方法。
        `lock`: 互斥锁，保证对全局变量的互斥性。指定校验字段或校验方法时，必须提供锁。

        注：
        1. 当不指定任何校验字段和校验方法，且 cmdSeesionsSpace 为空时，session 是一次性的
        2. 当发生同一 session 并行 get 后，后一次获取应该被拒绝，因此返回 None
        """
        if checkMethod is not None:
            async with lock: 
                session = self.__get_with_custom(event, cmdSessionsSpace, checkMethod)
        elif checkAttr is not None:
            async with lock: 
                session = self.__get_with_attr(event, cmdSessionsSpace, checkAttr)
        else:
            session = BotSession(cmdSessionsSpace)
            session._BotSession__add_event(event)
        
        if session is not None:
            session._BotSession__activated = True
        
        return session

    def __get_with_custom(
        self,
        event: BotEvent, 
        cmdSessionsSpace: List[BotSession],
        checkMethod: Callable[[BotEvent, BotEvent], bool]
    ) -> Union[BotSession, None]:
        """
        自定义校验后创建 session
        """
        for session in cmdSessionsSpace:
            if checkMethod(event, session.event):
                # 如果获取到的 session 是活跃状态，则驳回
                if session._BotSession__activated: 
                    return None

                session._BotSession__add_event(event)
                return session
        session = BotSession(cmdSessionsSpace)
        session._BotSession__add_event(event)
        cmdSessionsSpace.append(session)
        return session
    
    def __get_with_attr(
        self,
        event: BotEvent, 
        cmdSessionsSpace: List[BotSession],
        checkAttr: Union[Tuple[str, ...], str]
    ) -> Union[BotSession, None]:
        """
        event 属性校验后创建 session
        """
        if not (isinstance(checkAttr, str) or isinstance(checkAttr, tuple)):
            raise TypeError("不正确的校验属性格式")

        if isinstance(checkAttr, str):
            for session in cmdSessionsSpace:
                if getattr(session.event, checkAttr) == getattr(event, checkAttr):
                    # 如果获取到的 session 是活跃状态，则驳回
                    if session._BotSession__activated: 
                        return None

                    session._BotSession__add_event(event)
                    return session
        else:
            for session in cmdSessionsSpace:
                if Reflector.get(session.event, checkAttr) == Reflector.get(event, checkAttr):
                    # 如果获取到的 session 是活跃状态，则驳回
                    if session._BotSession__activated: 
                        return None

                    session._BotSession__add_event(event)
                    return session
        session = BotSession(cmdSessionsSpace)
        session._BotSession__add_event(event)
        cmdSessionsSpace.append(session)
        return session
