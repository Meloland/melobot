import asyncio as aio
import time
from abc import ABC, abstractmethod
from contextvars import ContextVar, Token
from functools import wraps

from ..interface.core import IActionResponder
from ..interface.typing import *
from .action import *
from .event import *
from .exceptions import BotInvalidSession

__all__ = [
    'BotSession',
    'BotSessionManager'
]

audio_msg = record_msg


class BotSession:
    """
    Bot Session 类。不需要直接实例化，必须通过 BotSessionBuilder 构造。
    """
    def __init__(self, responder: IActionResponder) -> None:
        super().__init__()
        self._expired = False
        self.store = {}
        self.crt_time = time.time()
        self.event_records: List[BotEvent] = []
        # session 是否空闲，如果空闲，则不能获取。应该等待或退出
        self._free_signal= aio.Event()
        self._free_signal.set()
        self._responder = responder

    def _add_event(self, event: BotEvent) -> None:
        if event is None:
            return
        self.event_records.append(event)

    @property
    def event(self) -> Union[BotEvent, None]: 
        try: 
            return next(reversed(self.event_records))
        except StopIteration: 
            return None

    def store_get(self, key: object) -> object: 
        return self.store[key]

    def store_add(self, key: object, val: object) -> None: 
        self.store[key] = val

    def store_update(self, store: Dict) -> None: 
        self.store.update(store)

    def store_remove(self, key: object) -> None: 
        self.store.pop(key)

    def store_clear(self) -> None: 
        self.store.clear()

    def destory(self) -> None:
        """
        销毁当前 session，销毁后清空 store, 无法再执行操作
        """
        if not self._expired:
            self.event_records.clear()
            self.store_clear()
            self._expired = True

    # 不要更改这个方法下的所有 typing，否则会影响被装饰方法的 typing
    def _launch(get_action):
        """
        action 构建方法的装饰器，
        在 action 构建后进行发送，以及完成响应等待
        """
        @wraps(get_action)
        async def wrapper(self: "BotSession", *args, **kwargs):
            if self._expired: raise BotInvalidSession("session 已无效，无法执行操作")

            action: BotAction = await get_action(self, *args, **kwargs)
            if action.resp_id is None:
                return await self._responder.take_action(action)
            else:
                return await (await self._responder.take_action_wait(action))
        return wrapper

    """以下所有 action 方法虽然本身不是异步的，但不使用 async，返回值将没有注解"""

    @_launch
    async def send(
        self, 
        content: Union[str, Msg, MsgSegment],
        enable_cq_str: bool=False,
        waitResp: bool=False
    ) -> Union[RespEvent, None]:
        """
        在当前 session 上下文下发送消息。
        enable_cq_str 若开启，文本中若包含 cq 字符串，将会被解释
        """
        action = msg_action(
            content, 
            self.event.is_private(),
            self.event.sender.id,
            self.event.group_id,
            waitResp,
            self.event
        )
        if enable_cq_str:
            action = cq_format(action)
        return action

    @_launch
    async def custom_send(
        self,
        content: Union[str, Msg, MsgSegment],
        isPrivate: bool,
        userId: int, 
        groupId: int=None,
        enable_cq_str: bool=False,
        waitResp: bool=False,
    ) -> Union[RespEvent, None]:
        """
        自定义发送消息。
        enable_cq_str 若开启，文本中若包含 cq 字符串，将会被解释
        """
        action = msg_action(
            content, 
            isPrivate, 
            userId, 
            groupId, 
            waitResp, 
            self.event
        )
        if enable_cq_str:
            action = cq_format(action)
        return action
    
    @_launch
    async def send_forward(
        self,
        msgNodes: MsgNodeList,
        enable_cq_str: bool=False,
        waitResp: bool=False
    ) -> Union[RespEvent, None]:
        """
        在当前 session 上下文下发送转发消息。
        enable_cq_str 若开启，文本中若包含 cq 字符串，将会被解释
        """
        action = forward_msg_action(
            msgNodes,
            self.event.is_private(),
            self.event.sender.id,
            self.event.group_id,
            waitResp,
            self.event
        )
        if enable_cq_str:
            action = cq_format(action)
        return action
    
    @_launch
    async def custom_send_forward(
        self,
        msgNodes: MsgNodeList,
        isPrivate: bool,
        userId: int=None, 
        groupId: int=None,
        enable_cq_str: bool=False,
        waitResp: bool=False,
    ) -> Union[RespEvent, None]:
        """
        自定义发送转发消息。
        enable_cq_str 若开启，文本中若包含 cq 字符串，将会被解释
        """
        action = forward_msg_action(
            msgNodes,
            isPrivate,
            userId,
            groupId,
            waitResp,
            self.event
        )
        if enable_cq_str:
            action = cq_format(action)
        return action
    
    @_launch
    async def recall(
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
    
    @_launch
    async def get_msg(
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
    
    @_launch
    async def get_forward_msg(
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
    
    @_launch
    async def mark_read(
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

    
    @_launch
    async def group_kick(
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
    
    @_launch
    async def group_ban(
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
    
    @_launch
    async def group_ban_anonymous(
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
        
    @_launch
    async def group_ban_all(
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
        
    @_launch
    async def group_leave(
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
    
    @_launch
    async def group_sign(
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
    
    
    @_launch
    async def get_group(
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
    
    @_launch
    async def get_groups(
        self
    ) -> Union[RespEvent, None]:
        """
        获取 bot 加入的群列表
        """
        return get_group_list_action(
            True,
            self.event
        )
        
    @_launch
    async def get_group_member(
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
    
    @_launch
    async def get_group_members(
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
        
    @_launch
    async def get_group_honor(
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
        
    @_launch
    async def get_group_file_sys(
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
    
    @_launch
    async def get_group_root_files(
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
    
    @_launch
    async def get_group_files_in_folder(
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
        
    @_launch
    async def get_group_file_url(
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
    
    @_launch
    async def get_group_sys_msg(
        self
    ) -> Union[RespEvent, None]:
        """
        获取群系统消息
        """
        return get_group_sys_msg_action(
            True,
            self.event
        )
    
    @_launch
    async def get_group_notices(
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
        
    @_launch
    async def get_group_records(
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
        
    @_launch
    async def get_group_essences(
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


    @_launch
    async def set_group_admin(
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
    
    @_launch
    async def set_group_card(
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
    
    @_launch
    async def set_group_name(
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
        
    @_launch
    async def set_group_title(
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
        
    @_launch
    async def process_group_add(
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
    
    @_launch
    async def set_group_icon(
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
    
    @_launch
    async def set_group_notice(
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
        
    @_launch
    async def set_group_essence(
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
        
    @_launch
    async def create_group_folder(
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
        
    @_launch
    async def delete_group_folder(
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
        
    @_launch
    async def delete_group_file(
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


    @_launch
    async def get_friends(
        self
    ) -> Union[RespEvent, None]:
        """
        获取好友列表
        """
        return get_friend_list_action(
            True,
            self.event
        )
        
    @_launch
    async def get_undirect_friends(
        self
    ) -> Union[RespEvent, None]:
        """
        获取单向好友列表
        """
        return get_undirect_friend_action(
            True,
            self.event
        )
    
    @_launch
    async def get_user(
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
        
    @_launch
    async def process_friend_add(
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
    
    @_launch
    async def delete_friend(
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
        
    @_launch
    async def delete_undirect_friend(
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
    

    
    @_launch
    async def get_login_info(
        self,
    ) -> Union[RespEvent, None]:
        """
        获得登录号信息
        """
        return get_login_info_action(
            True,
            self.event
        )
    
    @_launch
    async def set_login_profile(
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
    
    @_launch
    async def check_send_image(
        self
    ) -> Union[RespEvent, None]:
        """
        检查是否可以发送图片
        """
        return check_send_image_action(
            True,
            self.event
        )
        
    @_launch
    async def check_send_audio(
        self
    ) -> Union[RespEvent, None]:
        """
        检查是否可以发送语音
        """
        return check_send_record_action(
            True,
            self.event
        )
    
    @_launch
    async def get_cq_status(
        self
    ) -> Union[RespEvent, None]:
        """
        获取 go-cqhttp 状态
        """
        return get_cq_status_action(
            True,
            self.event
        )
    
    @_launch
    async def get_cq_version(
        self
    ) -> Union[RespEvent, None]:
        """
        获取 go-cqhttp 版本信息
        """
        return get_cq_version_action(
            True,
            self.event
        )
        
    @_launch
    async def quick_handle(
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
    
    @_launch
    async def get_image(
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
    
    @_launch
    async def download_file(
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
        
    @_launch
    async def ocr(
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
    
    @_launch
    async def upload_file(
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
    
    @_launch
    async def get_at_all_remain(
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
    
    @_launch
    async def get_online_clients(
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
    
    @_launch
    async def get_model_show(
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
    
    @_launch
    async def set_model_show(
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


class SessionRule(ABC):
    """
    用作 sesion 的区分依据
    """
    def __init__(self) -> None:
        pass

    @abstractmethod
    def verify(cls, e1: BotEvent, e2: BotEvent) -> bool:
        pass


class BotSessionManager:
    @classmethod
    async def get(cls, event: BotEvent, responder: IActionResponder, working_lock: aio.Lock=None, check_rule: SessionRule=None, 
                  session_space: List[BotSession]=None, conflict_wait: bool=False
                  ) -> Union[BotSession, None]:
        """
        当 check_rule 为空时，每次生成临时 session，且不在 session_space 中保存。
        如果提供 check_rule，则必须同时提供 session_space
        如果获取到的 session 在活跃状态，则返回 None。
        """
        if check_rule:
            # session_space, session free_signal 竞争，需要加锁
            async with working_lock:
                session = await cls._make_with_rule(event, responder, check_rule, session_space, conflict_wait)
                if session: session._free_signal.clear()
                return session
        else:
            return await cls._make(event, responder)
        
    @classmethod
    def recycle(cls,session: BotSession) -> None:
        """
        回收当前 session，使当前 session 状态变为 free
        """
        session._free_signal.set()

    @classmethod
    async def _make(cls, event: BotEvent, responder: IActionResponder, session_space: List[BotSession]=None) -> BotSession:
        """
        获取一次性 session
        """
        session = BotSession(responder)
        session._add_event(event)
        if session_space is not None: 
            session_space.append(session)
        return session

    @classmethod
    async def _make_with_rule(cls, event: BotEvent, responder: IActionResponder, check_rule: SessionRule, 
                              session_space: List[BotSession], conflict_wait: bool=False
                             ) -> Union[BotSession, None]:
        """
        根据规则获取 session
        """
        for session in session_space:
            if check_rule.verify(session.event, event):
                if session._free_signal.is_set():
                    session._add_event(event)
                    return session
                
                if not conflict_wait:
                    return None
                
                await session._free_signal.wait()
                if session._expired:
                    session_space.remove(session)
                    return await cls._make(event, responder, session_space)
                else:
                    session._add_event(event)
                    return session

        return await cls._make(event, responder, session_space)


_session_ctx = ContextVar("session_ctx")


class SessionLocal:
    """
    session 自动上下文
    """
    __slots__ = tuple(
        list(
            filter(lambda x: not (len(x) >= 2 and x[:2] == '__'), dir(BotSession))
        ) + ['__storage__']
    )

    def __init__(self) -> None:
        object.__setattr__(self, '__storage__', _session_ctx)
        self.__storage__: ContextVar[BotSession]

    def __setattr__(self, __name: str, __value: Any) -> None:
        setattr(self.__storage__.get(), __name, __value)

    def __getattr__(self, __name: str) -> Any:
        return getattr(self.__storage__.get(), __name)
    
    def _add_ctx(self, ctx: BotSession) -> Token:
        return self.__storage__.set(ctx)
    
    def _del_ctx(self, token: Token) -> None:
        self.__storage__.reset(token)


SESSION_LOCAL = SessionLocal()