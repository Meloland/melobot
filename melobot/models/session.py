import asyncio as aio
import time
from abc import ABC, abstractmethod
from contextvars import ContextVar, Token
from functools import wraps

from ..interface.core import IActionResponder
from ..interface.typing import *
from ..interface.exceptions import *
from ..utils.parser import ParseArgs
from .action import *
from .event import *


__all__ = [
    'BotSession',
    'BotSessionManager'
]

audio_msg = record_msg


class BotSession:
    """
    Bot Session 类。不需要直接实例化，必须通过 BotSessionBuilder 构造。
    """
    def __init__(self, responder: IActionResponder, handler_ref: object) -> None:
        super().__init__()
        self.store = {}
        self.crt_time = time.time()
        self.hup_times: List[float] = []
        self.events: List[BotEvent] = []
        self.args_list: List[ParseArgs] = []
        self._responder = responder

        # session 是否空闲的标志，由 BotSessionManager 修改和管理
        self._free_signal = aio.Event()
        self._free_signal.set()
        # session 是否挂起的标志，由 BotSessionManager 修改和管理。注意 session 挂起时一定是非空闲和非过期的
        self._awake_signal = aio.Event()
        self._awake_signal.set()
        # session 是否过期的标志，由 BotSessionManager 修改和管理
        self._expired = False
        # 用于标记该 session 属于哪个 session 空间，如果为 None 则表明是空 session（供生命周期钩子方法使用）或是一次性 session
        self._space_tag: Union[object, None] = handler_ref

    def _append_records(self, event: BotEvent) -> None:
        """
        添加新的记录。包含新的事件、或可能存在的事件解析参数（如果不存在，添加为 None）。
        """
        self.events.append(event)
        handler = self._space_tag
        args = handler._pop_args(event)
        self.args_list.append(args)

    @property
    def event(self) -> Union[BotEvent, None]: 
        try: 
            return next(reversed(self.events))
        except StopIteration: 
            return None

    @property
    def last_hup(self) -> Union[float, None]:
        try:
            return next(reversed(self.hup_times))
        except StopIteration:
            return None

    @property
    def args(self) -> Union[ParseArgs, None]:
        try:
            return next(reversed(self.args_list))
        except StopIteration:
            return None

    async def suspend(self) -> None:
        """
        当前 session 挂起（也就是所在方法的挂起）。直到满足同一 session_rule 的事件重新进入，
        session 所在方法便会被唤醒
        """
        BotSessionManager._hup(self)
        await self._awake_signal.wait()

    def destory(self) -> None:
        """
        标记当前 session 为 expired，清空事件缓存、挂起时间缓存和存储。
        此方法执行后，session 所在的事件执行方法或生命周期钩子方法依然可以运行，但无法再执行 action 操作。
        真正的销毁需要等待事件执行方法或生命周期钩子方法运行结束，由 BotSessionManager.recycle 完成。

        同时特别注意：在标记销毁后，其他异步协程就不会附着到此 session，而是产生一个新的 session 替代。
        标记销毁后如果你访问了临界区资源，则可能发生冲突。因此建议在最后执行 destory
        """
        BotSessionManager._expire(self)

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

    # 不要更改这个方法下的所有 typing，否则会影响被装饰方法的 typing
    def _launch(get_action):
        """
        action 构建方法的装饰器，
        在 action 构建后进行发送，以及完成响应等待
        """
        @wraps(get_action)
        async def wrapper(self: "BotSession", *args, **kwargs):
            if self._expired: raise BotInvalidSession("session 已标记过期，无法执行 action 操作")

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
    STORAGE: Dict[object, Set[BotSession]] = {}
    LOCK_STORAGE: Dict[object, aio.Lock] = {}
    HUP_STORAGE: Dict[object, Set[BotSession]] = {}

    @classmethod
    def register(cls, handler: object) -> None:
        """
        以 handler 为键，注册 handler 对应的 session 空间、操作锁和挂起 session 空间
        """
        if cls.STORAGE.get(handler) is None:
            cls.STORAGE[handler] = set()
            cls.LOCK_STORAGE[handler] = aio.Lock()
            cls.HUP_STORAGE[handler] = set()
        else:
            raise BotException("预期之外的 session 存储重复初始化")

    @classmethod
    def _hup(cls, session: BotSession) -> None:
        """
        挂起 session。应该由 session.suspend 调用
        """
        if session._space_tag is None:
            raise BotException("一次性 session 或空 session 不支持挂起，因为缺乏 session_rule 作为唤醒标志")
        elif session._expired:
            raise BotException("过期的 session 不能被挂起")
        else:
            session.hup_times.append(time.time())
        session._awake_signal.clear()
        cls.STORAGE[session._space_tag].remove(session)
        cls.HUP_STORAGE[session._space_tag].add(session)

    @classmethod
    def _rouse(cls, session: BotSession) -> None:
        """
        唤醒 session。应该由 cls._get_on_rule 调用
        """
        cls.HUP_STORAGE[session._space_tag].remove(session)
        cls.STORAGE[session._space_tag].add(session)
        session._awake_signal.set()

    @classmethod
    def _expire(cls, session: BotSession) -> None:
        """
        标记该 session 为过期状态。实际的销毁交由 cls.recycle 处理
        """
        if not session._expired:
            session.events.clear()
            session.hup_times.clear()
            session.store_clear()
            session._expired = True

    @classmethod
    def recycle(cls, session: BotSession) -> None:
        """
        事件执行方法或生命周期钩子方法运行结束后，重置 session._free_signal 使 session 变为空闲。
        同时判断 session 是否有所属空间标记，有则需要过期检查和销毁
        """
        session._free_signal.set()
        if session._space_tag is None or not session._expired:
            return
        cls.STORAGE[session._space_tag].remove(session)

    @classmethod
    async def get(cls, event: BotEvent, responder: IActionResponder, handler: object, forbid_rule: bool=False) -> Union[BotSession, None, Literal['attached']]:
        """
        handler 存在 session_rule 则表明需要映射到一个 session_space 进行存储。
        不存在 session_rule 则会生成一次性 session 或空 session（供生命周期钩子方法使用），而不存储。
        如果获取的 session 非空闲，且 handler 决定此时放弃本次获取，则返回 None。
        如果附着在一个挂起 session 上，则返回 'attached'。

        如果 forbid_rule 为 True，则强制不使用 session_rule
        """
        if handler:
            session_rule, working_lock = handler._session_rule, cls.LOCK_STORAGE[handler]
        else:
            session_rule, working_lock = None, None

        if forbid_rule:
            session_rule = None
        
        if session_rule:
            # session_space, session._free_signal 竞争，需要加锁
            async with working_lock:
                session = await cls._get_on_rule(event, responder, handler)
                # 必须在锁的保护下修改 session._free_signal
                if session and not isinstance(session, str): 
                    session._free_signal.clear()
        else:
            session = cls._make(event, responder, handler)
            session._free_signal.clear()
        
        return session

    @classmethod
    def _make(cls, event: BotEvent, responder: IActionResponder, handler: object=None, session_space: Set[BotSession]=None) -> BotSession:
        """
        获取 session。
        如果不存在 session_space，则返回的是一次性 session。
        如果不存在 event，则返回的是空 session（供生命周期钩子方法使用）
        """
        session = BotSession(responder, handler)
        if event:
            session._append_records(event)
        # 必须使用 is not None，因为空容器 if 取值为 False
        if session_space is not None:
            session_space.add(session)
        return session

    @classmethod
    async def _get_on_rule(cls, event: BotEvent, responder: IActionResponder, handler: object) -> Union[BotSession, None, Literal['attached']]:
        """
        根据 handler 具体情况，从对应 session_space 中获取 session 或新建 session。
        或从 hup_session_space 中唤醒 session，或返回 None
        """
        session = None
        check_rule, session_space, hup_session_space, conflict_wait = \
            handler._session_rule, cls.STORAGE[handler], cls.HUP_STORAGE[handler], handler._wait_flag
        
        # for 循环都需要即时 break，保证遍历 session_space 时没有协程切换。因为切换后 session_space 可能发生变动
        for s in hup_session_space:
            # session 的挂起方法，保证 session 一定未过期，因此不进行过期检查
            if check_rule.verify(s.event, event):
                session = s
                break
        # 如果获得一个挂起的 session，它一定是可附着的，附着并唤醒后告诉外界是附着执行
        if session:
            session._append_records(event)
            cls._rouse(session)
            return 'attached'
        # 如果不匹配任何已挂起的 session，则查看普通的 session_space（包含所有非挂起 session）
        for s in session_space:
            if check_rule.verify(s.event, event) and not s._expired:
                session = s
                break
        
        # 如果会话不存在，生成一个新 session 变量
        if session is None:
            return cls._make(event, responder, handler, session_space)
        # 如果会话存在，且未过期，且空闲，则附着到这个 session 上
        if session._free_signal.is_set():
            session._append_records(event)
            return session
        # 如果会话存在，且未过期，但是不空闲，选择不等待
        if not conflict_wait:
            return None
        # 如果会话存在，且未过期，但是不空闲，选择等待，此时就不得不陷入等待（即将发生协程切换）
        else:
            await session._free_signal.wait()

        """
        重新切换回本协程后，session 有可能变为过期，但此时一定是空闲的。
        同时一定是非挂起状态。因为恢复空闲只在 cls.recycle 进行，此时一定是非挂起状态了。
        即使该 session 因过期被所在的 session_space 清除也无妨，因为此处有引用，
        该 session 并不会消失。且此处不操作 session_space，无需担心 session_space 变动
        """
        # 如果过期，生成一个新的 session 变量
        if session._expired:
            return cls._make(event, responder, handler, session_space)
        # 如果未过期，则附着到这个 session 上
        else:
            session._append_records(event)
            return session


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