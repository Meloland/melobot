import asyncio as aio
import time
from contextvars import ContextVar, Token
from copy import deepcopy
from functools import wraps

from melobot.models.event import BotEvent

from ..models.base import get_twin_event
from ..types.core import AbstractResponder
from ..types.exceptions import *
from ..types.models import SessionRule
from ..types.typing import *
from .action import *
from .event import *


class BotSession:
    """
    Bot Session 类。不需要直接实例化，必须通过 BotSessionBuilder 构造。
    """

    def __init__(
        self,
        manager: Type["BotSessionManager"],
        responder: AbstractResponder,
        space_tag: object = None,
    ) -> None:
        super().__init__()
        self.store = {}
        self.timestamp = time.time()
        self.hup_times: List[float] = []
        self.events: List[MessageEvent | RequestEvent | MetaEvent | NoticeEvent] = []

        self._manager = manager
        self._responder = responder
        # session 是否空闲的标志，由 BotSessionManager 修改和管理
        self._free_signal = aio.Event()
        self._free_signal.set()
        # session 是否挂起的标志。二者互为孪生反状态。由 BotSessionManager 修改和管理
        # 注意 session 挂起时一定是非空闲和非过期的
        self._hup_signal, self._awake_signal = get_twin_event()
        # session 是否过期的标志，由 BotSessionManager 修改和管理
        self._expired = False
        # 用于标记该 session 属于哪个 session 空间，如果为 None 则表明是空 session 或是一次性 session
        # 其实这里如果传入 space_tag 则一定是所属 handler 的引用
        self._space_tag: Optional[object] = space_tag
        # 所属 handler 的引用（和 space_tag 不一样，所有在 handler 中产生的 session，此属性必为非空）
        self._handler: object = None

    @property
    def event(
        self,
    ) -> MessageEvent | RequestEvent | MetaEvent | NoticeEvent:
        try:
            return next(reversed(self.events))
        except StopIteration:
            raise BotSessionError("当前 session 下不存在可用的 event")

    @property
    def last_hup(self) -> Optional[float]:
        try:
            return next(reversed(self.hup_times))
        except StopIteration:
            return None

    @property
    def args(self):
        if self._handler is not None and self.event._args_map is not None:
            args_group = self.event._args_map.get(self._handler.parser.id)
            if self._handler.parser.target is None:
                return deepcopy(args_group)
            for cmd_name in self._handler.parser.target:
                args = args_group.get(cmd_name)
                if args is not None:
                    return deepcopy(args.vals)
            raise BotSessionError("尝试获取的命令解析参数不存在")
        return None

    async def hup(self, overtime: int = None) -> None:
        """
        当前 session 挂起（也就是所在方法的挂起）。直到满足同一 session_rule 的事件重新进入，
        session 所在方法便会被唤醒。但如果设置了超时时间且在唤醒前超时，则会强制唤醒 session，
        并抛出 BotHupTimeout 异常
        """
        self._manager._hup(self)
        if overtime is None:
            await self._awake_signal.wait()
        elif overtime <= 0:
            raise BotSessionError("session 挂起超时时间（秒数）必须 > 0")
        else:
            await aio.wait(
                [self._awake_signal.wait(), aio.sleep(overtime)],
                return_when=aio.FIRST_COMPLETED,
            )
            if self._awake_signal.is_set():
                return
            self._manager._rouse(self)
            raise SessionHupTimeout("session 挂起超时")

    def destory(self) -> None:
        """
        销毁方法。
        其他 session 调用会立即清空 session 存储、事件记录、挂起时间记录。
        如果调用 session 有 space_tag，还会从存储空间中移除该 session
        """
        if self.event is None:
            pass
        else:
            self._manager._expire(self)

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
    def _action_launch(get_action):
        """
        action 构建方法的装饰器，
        在 action 构建后进行发送，以及完成响应等待
        """

        @wraps(get_action)
        async def wrapper(self: "BotSession", *args, **kwargs):
            if self._expired:
                raise BotSessionError("session 已标记为过期，无法执行 action 操作")

            action: BotAction = await get_action(self, *args, **kwargs)
            if len(self.events) > 0:
                action._fill_trigger(self.event)

            if action.resp_id is None:
                return await self._responder.take_action(action)
            else:
                return await (await self._responder.take_action_wait(action))

        return wrapper

    """以下所有 action 方法虽然本身不是异步的，但不使用 async，返回值将没有注解"""

    @_action_launch
    async def custom_action(self, action: BotAction) -> Optional[ResponseEvent]:
        """
        直接处理提供的 action
        """
        return action

    @_action_launch
    async def send(
        self,
        content: str | CQMsgDict | List[CQMsgDict],
        cq_str: bool = False,
        waitResp: bool = False,
    ) -> Optional[ResponseEvent]:
        """
        在当前 session 上下文下发送消息。
        cq_str 若开启，文本中若包含 cq 字符串，将会被解释
        """
        if self.event == None:
            raise BotSessionError("空 session 需要使用 custom_send 方法替代 send")
        action = msg_action(
            content,
            self.event.is_private(),
            self.event.sender.id,
            self.event.group_id,
            waitResp,
        )
        if cq_str:
            action = to_cq_str_action(action)
        return action

    @_action_launch
    async def custom_send(
        self,
        content: str | CQMsgDict | List[CQMsgDict],
        isPrivate: bool,
        userId: int = None,
        groupId: int = None,
        cq_str: bool = False,
        waitResp: bool = False,
    ) -> Optional[ResponseEvent]:
        """
        自定义发送消息。
        cq_str 若开启，文本中若包含 cq 字符串，将会被解释
        """
        if isPrivate and userId is None:
            raise BotActionError("为私聊时，构建 action 必须提供 userId 参数")
        if not isPrivate and groupId is None:
            raise BotActionError("为群聊时，构建 action 必须提供 groupId 参数")
        action = msg_action(content, isPrivate, userId, groupId, waitResp, None)
        if cq_str:
            action = to_cq_str_action(action)
        return action

    @_action_launch
    async def send_forward(
        self,
        msgNodes: List[MsgNodeDict],
        cq_str: bool = False,
        waitResp: bool = False,
    ) -> Optional[ResponseEvent]:
        """
        在当前 session 上下文下发送转发消息。
        cq_str 若开启，文本中若包含 cq 字符串，将会被解释
        """
        if self.event == None:
            raise BotSessionError(
                "空 session 需要使用 custom_send_forward 方法替代 send_forward"
            )
        action = forward_msg_action(
            msgNodes,
            self.event.is_private(),
            self.event.sender.id,
            self.event.group_id,
            waitResp,
        )
        if cq_str:
            action = to_cq_str_action(action)
        return action

    @_action_launch
    async def custom_send_forward(
        self,
        msgNodes: List[MsgNodeDict],
        isPrivate: bool,
        userId: int = None,
        groupId: int = None,
        cq_str: bool = False,
        waitResp: bool = False,
    ) -> Optional[ResponseEvent]:
        """
        自定义发送转发消息。
        cq_str 若开启，文本中若包含 cq 字符串，将会被解释
        """
        action = forward_msg_action(msgNodes, isPrivate, userId, groupId, waitResp)
        if cq_str:
            action = to_cq_str_action(action)
        return action

    @_action_launch
    async def recall(
        self, msgId: int, waitResp: bool = False
    ) -> Optional[ResponseEvent]:
        """
        撤回消息
        """
        return msg_del_action(msgId, waitResp)

    @_action_launch
    async def get_msg(self, msgId: int) -> ResponseEvent:
        """
        获取消息信息
        """
        return get_msg_action(msgId, True)

    @_action_launch
    async def get_forward_msg(
        self,
        forwardId: str,
    ) -> ResponseEvent:
        """
        获取转发消息信息
        """
        return get_forward_msg_action(forwardId, True)

    @_action_launch
    async def mark_read(
        self, msgId: int, waitResp: bool = False
    ) -> Optional[ResponseEvent]:
        """
        标记为已读
        """
        return mark_msg_read_action(msgId, waitResp)

    @_action_launch
    async def group_kick(
        self,
        groupId: int,
        userId: int,
        laterReject: bool = False,
        waitResp: bool = False,
    ) -> Optional[ResponseEvent]:
        """
        群组踢人
        """
        return group_kick_action(groupId, userId, laterReject, waitResp)

    @_action_launch
    async def group_ban(
        self,
        groupId: int,
        userId: int,
        duration: int,
        waitResp: bool = False,
    ) -> Optional[ResponseEvent]:
        """
        群组禁言。
        duration 为 0 取消禁言
        """
        return group_ban_action(groupId, userId, duration, waitResp)

    @_action_launch
    async def group_ban_anonymous(
        self,
        groupId: int,
        anonymFlag: str,
        duration: int,
        waitResp: bool = False,
    ) -> Optional[ResponseEvent]:
        """
        群组匿名禁言。
        无法取消禁言
        """
        return group_anonym_ban_action(groupId, anonymFlag, duration, waitResp)

    @_action_launch
    async def group_ban_all(
        self,
        groupId: int,
        enable: bool,
        waitResp: bool = False,
    ) -> Optional[ResponseEvent]:
        """
        群组全员禁言
        """
        return group_whole_ban_action(groupId, enable, waitResp)

    @_action_launch
    async def group_leave(
        self,
        groupId: int,
        isDismiss: bool,
        waitResp: bool = False,
    ) -> Optional[ResponseEvent]:
        """
        退出群组
        """
        return group_leave_action(groupId, isDismiss, waitResp)

    @_action_launch
    async def group_sign(
        self,
        groupId: int,
        waitResp: bool = False,
    ) -> Optional[ResponseEvent]:
        """
        群组打卡
        """
        return group_sign_action(groupId, waitResp)

    @_action_launch
    async def get_group(
        self,
        groupId: int,
        noCache: bool,
    ) -> ResponseEvent:
        """
        获取群信息
        """
        return get_group_info_action(groupId, noCache, True)

    @_action_launch
    async def get_groups(self) -> ResponseEvent:
        """
        获取 bot 加入的群列表
        """
        return get_group_list_action(True)

    @_action_launch
    async def get_group_member(
        self,
        groupId: int,
        userId: int,
        noCache: bool,
    ) -> ResponseEvent:
        """
        获取群内单独一个群成员信息
        """
        return get_group_member_info_action(groupId, userId, noCache, True)

    @_action_launch
    async def get_group_members(
        self,
        groupId: int,
        noCache: bool,
    ) -> ResponseEvent:
        """
        获取群成员列表
        """
        return get_group_member_list_action(groupId, noCache, True)

    @_action_launch
    async def get_group_honor(
        self,
        groupId: int,
        type: Literal[
            "talkative", "performer", "legend", "strong_newbie", "emotion", "all"
        ],
    ) -> ResponseEvent:
        """
        获取群荣誉信息
        """
        return get_group_honor_action(groupId, type, True)

    @_action_launch
    async def get_group_file_sys(
        self,
        groupId: int,
    ) -> ResponseEvent:
        """
        获取群文件系统信息
        """
        return get_group_filesys_info_action(
            groupId,
            True,
        )

    @_action_launch
    async def get_group_root_files(
        self,
        groupId: int,
    ) -> ResponseEvent:
        """
        获取群根目录文件列表
        """
        return get_group_root_files_action(
            groupId,
            True,
        )

    @_action_launch
    async def get_group_files_in_folder(
        self, groupId: int, folderId: str
    ) -> ResponseEvent:
        """
        获取群子目录文件列表
        """
        return get_group_files_byfolder_action(
            groupId,
            folderId,
            True,
        )

    @_action_launch
    async def get_group_file_url(
        self, groupId: int, fileId: str, fileTypeId: int
    ) -> ResponseEvent:
        """
        获取群文件资源链接。文件相关信息通过 `get_group_root_files` 或
        `get_group_files` 的响应获得
        """
        return get_group_file_url_action(
            groupId,
            fileId,
            fileTypeId,
            True,
        )

    @_action_launch
    async def get_group_sys_msg(self) -> ResponseEvent:
        """
        获取群系统消息
        """
        return get_group_sys_msg_action(
            True,
        )

    @_action_launch
    async def get_group_notices(
        self,
        groupId: int,
    ) -> ResponseEvent:
        """
        获取群公告。
        群公告图片有 id，但暂时没有下载的方法
        """
        return get_group_notice_action(
            groupId,
            True,
        )

    @_action_launch
    async def get_group_records(self, msgSeq: int, groupId: int) -> ResponseEvent:
        """
        获取群消息历史记录
        """
        return get_group_msg_history_action(
            msgSeq,
            groupId,
            True,
        )

    @_action_launch
    async def get_group_essences(self, groupId: int) -> ResponseEvent:
        """
        获取精华消息列表
        """
        return get_group_essence_list_action(
            groupId,
            True,
        )

    @_action_launch
    async def set_group_admin(
        self, groupId: int, userId: int, enable: bool, waitResp: bool = False
    ) -> Optional[ResponseEvent]:
        """
        设置群管理员
        """
        return set_group_admin_action(
            groupId,
            userId,
            enable,
            waitResp,
        )

    @_action_launch
    async def set_group_card(
        self, groupId: int, userId: int, card: str, waitResp: bool = False
    ) -> Optional[ResponseEvent]:
        """
        设置群名片
        """
        return set_group_card_action(
            groupId,
            userId,
            card,
            waitResp,
        )

    @_action_launch
    async def set_group_name(
        self, groupId: int, name: str, waitResp: bool = False
    ) -> Optional[ResponseEvent]:
        """
        设置群名
        """
        return set_group_name_action(
            groupId,
            name,
            waitResp,
        )

    @_action_launch
    async def set_group_title(
        self,
        groupId: int,
        userId: int,
        title: str,
        duration: int = -1,
        waitResp: bool = False,
    ) -> Optional[ResponseEvent]:
        """
        设置群头衔
        """
        return set_group_title_action(
            groupId,
            userId,
            title,
            duration,
            waitResp,
        )

    @_action_launch
    async def process_group_add(
        self,
        addFlag: str,
        addType: Literal["add", "invite"],
        approve: bool,
        rejectReason: str = None,
        waitResp: bool = False,
    ) -> Optional[ResponseEvent]:
        """
        处理加群请求
        """
        return set_group_add_action(
            addFlag,
            addType,
            approve,
            rejectReason,
            waitResp,
        )

    @_action_launch
    async def set_group_icon(
        self, groupId: int, file: str, cache: Literal[0, 1] = 0, waitResp: bool = False
    ) -> Optional[ResponseEvent]:
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
        )

    @_action_launch
    async def set_group_notice(
        self, groupId: int, content: str, imageUrl: str = None, waitResp: bool = False
    ) -> Optional[ResponseEvent]:
        """
        发送群公告。
        注意 `imageUrl` 只能为本地 url，示例：`file:///C:/users/15742/desktop/123.jpg`
        """
        return set_group_notice_action(
            groupId,
            content,
            imageUrl,
            waitResp,
        )

    @_action_launch
    async def set_group_essence(
        self, msgId: int, type: Literal["add", "del"], waitResp: bool = False
    ) -> Optional[ResponseEvent]:
        """
        设置群精华消息
        """
        return set_group_essence_action(
            msgId,
            type,
            waitResp,
        )

    @_action_launch
    async def create_group_folder(
        self, groupId: int, folderName: str, waitResp: bool = False
    ) -> Optional[ResponseEvent]:
        """
        创建群文件夹。注意：只能在根目录创建文件夹
        """
        return create_group_folder_action(
            groupId,
            folderName,
            waitResp,
        )

    @_action_launch
    async def delete_group_folder(
        self, groupId: int, folderId: str, waitResp: bool = False
    ) -> Optional[ResponseEvent]:
        """
        删除群文件夹
        """
        return delete_group_folder_action(
            groupId,
            folderId,
            waitResp,
        )

    @_action_launch
    async def delete_group_file(
        self, groupId: int, fileId: str, fileTypeId: int, waitResp: bool = False
    ) -> Optional[ResponseEvent]:
        """
        删除群文件。文件相关信息通过 `get_group_root_files` 或
        `get_group_files` 的响应获得
        """
        return delete_group_file_action(
            groupId,
            fileId,
            fileTypeId,
            waitResp,
        )

    @_action_launch
    async def get_friends(self) -> ResponseEvent:
        """
        获取好友列表
        """
        return get_friend_list_action(
            True,
        )

    @_action_launch
    async def get_undirect_friends(self) -> ResponseEvent:
        """
        获取单向好友列表
        """
        return get_undirect_friend_action(
            True,
        )

    @_action_launch
    async def get_user(
        self,
        userId: int,
        noCache: bool,
    ) -> ResponseEvent:
        """
        获取用户信息。可以对陌生人或好友使用
        """
        return get_stranger_info_action(
            userId,
            noCache,
            True,
        )

    @_action_launch
    async def process_friend_add(
        self, addFlag: str, approve: bool, remark: str, waitResp: bool = False
    ) -> Optional[ResponseEvent]:
        """
        处理加好友。注意 remark 目前暂未实现
        """
        return set_friend_add_action(
            addFlag,
            approve,
            remark,
            waitResp,
        )

    @_action_launch
    async def delete_friend(
        self, userId: int, waitResp: bool = False
    ) -> Optional[ResponseEvent]:
        """
        删除好友
        """
        return delete_friend_action(
            userId,
            waitResp,
        )

    @_action_launch
    async def delete_undirect_friend(
        self, userId: int, waitResp: bool = False
    ) -> Optional[ResponseEvent]:
        """
        删除单向好友
        """
        return delete_undirect_friend_action(
            userId,
            waitResp,
        )

    @_action_launch
    async def get_login_info(self) -> ResponseEvent:
        """
        获得登录号信息
        """
        return get_login_info_action(True)

    @_action_launch
    async def set_login_profile(
        self,
        nickname: str,
        company: str,
        email: str,
        college: str,
        personalNote: str,
        waitResp: bool = False,
    ) -> Optional[ResponseEvent]:
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
        )

    @_action_launch
    async def check_send_image(self) -> ResponseEvent:
        """
        检查是否可以发送图片
        """
        return check_send_image_action(
            True,
        )

    @_action_launch
    async def check_send_audio(self) -> ResponseEvent:
        """
        检查是否可以发送语音
        """
        return check_send_record_action(
            True,
        )

    @_action_launch
    async def get_cq_status(self) -> ResponseEvent:
        """
        获取 go-cqhttp 状态
        """
        return get_cq_status_action(
            True,
        )

    @_action_launch
    async def get_cq_version(self) -> ResponseEvent:
        """
        获取 go-cqhttp 版本信息
        """
        return get_cq_version_action(
            True,
        )

    @_action_launch
    async def quick_handle(
        self,
        contextEvent: BotEvent,
        operation: dict,
        waitResp: bool = False,
    ) -> Optional[ResponseEvent]:
        """
        事件快速操作（该方法下一版本实现，本版本无法使用）
        """
        raise ReferenceError("该方法下一版本实现，本版本无法使用")
        # return quick_handle_action(
        #     contextEvent,
        #     operation,
        #     waitResp
        # )

    @_action_launch
    async def get_image(self, fileName: str) -> ResponseEvent:
        """
        获取图片信息
        """
        return get_image_action(
            fileName,
            True,
        )

    @_action_launch
    async def download_file(
        self,
        fileUrl: str,
        useThreadNum: int,
        headers: list | str,
        waitResp: bool = True,
    ) -> Optional[ResponseEvent]:
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
        )

    @_action_launch
    async def ocr(
        self,
        image: str,
    ) -> ResponseEvent:
        """
        图片 OCR。image 为图片 ID
        """
        return ocr_action(
            image,
            True,
        )

    @_action_launch
    async def upload_file(
        self,
        isPrivate: bool,
        file: str,
        sendFileName: str,
        userId: int = None,
        groupId: int = None,
        groupFolderId: str = None,
        waitResp: bool = False,
    ) -> Optional[ResponseEvent]:
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
        )

    @_action_launch
    async def get_at_all_remain(self, groupId: int) -> ResponseEvent:
        """
        获取群 @全体成员 剩余次数
        """
        return get_atall_remain_action(
            groupId,
            True,
        )

    @_action_launch
    async def get_online_clients(
        self,
        noCache: bool,
    ) -> ResponseEvent:
        """
        获取当前账号在线客户端列表
        """
        return get_online_clients_action(
            noCache,
            True,
        )

    @_action_launch
    async def get_model_show(
        self,
        model: str,
    ) -> ResponseEvent:
        """
        获取在线机型
        """
        return get_model_show_action(
            model,
            True,
        )

    @_action_launch
    async def set_model_show(self, model: str, modelShow: str) -> ResponseEvent:
        """
        设置在线机型
        """
        return set_model_show_action(
            model,
            modelShow,
            True,
        )


class BotSessionManager:
    STORAGE: Dict[object, Set[BotSession]] = {}
    HUP_STORAGE: Dict[object, Set[BotSession]] = {}
    # 各个 handler 对饮的操作锁
    WORK_LOCKS: Dict[object, aio.Lock] = {}
    # 用来标记 cls.get 等待一个挂起的 session 时的死锁
    DEADLOCK_FLAGS: Dict[object, aio.Event] = {}
    # 对应每个 handler 的 try_attach 过程的操作锁
    ATTACH_LOCKS: Dict[object, aio.Lock] = {}

    @classmethod
    def register(cls, handler: object) -> None:
        """
        以 handler 为键，注册 handler 对应的 session 空间、操作锁和挂起 session 空间
        """
        cls.STORAGE[handler] = set()
        cls.WORK_LOCKS[handler] = aio.Lock()
        cls.HUP_STORAGE[handler] = set()
        cls.DEADLOCK_FLAGS[handler] = aio.Event()
        cls.ATTACH_LOCKS[handler] = aio.Lock()

    @classmethod
    def inject(cls, session: BotSession, handler: object) -> None:
        """
        handler 内绑定 handler 引用到 session
        """
        session._handler = handler

    @classmethod
    def __attach(cls, event: BotEvent, handler: object) -> bool:
        """
        session 附着操作，临界区操作。只能在 cls.try_attach 中进行
        """
        session = None
        for s in cls.HUP_STORAGE[handler]:
            # session 的挂起方法，保证 session 一定未过期，因此不进行过期检查
            if handler._rule.compare(s.event, event):
                session = s
                break
        # 如果获得一个挂起的 session，它一定是可附着的，附着后需要唤醒
        if session:
            session.events.append(event)
            cls._rouse(session)
            return True
        return False

    @classmethod
    async def try_attach(cls, event: BotEvent, handler: object) -> bool:
        """
        检查是否有挂起的 session 可供 event 附着。
        如果有则附着并唤醒，并返回 True。否则返回 False。
        """
        if handler._rule is None:
            return False

        async with cls.ATTACH_LOCKS[handler]:
            t1 = aio.create_task(cls.DEADLOCK_FLAGS[handler].wait(), name="flag")
            t2 = aio.create_task(cls.WORK_LOCKS[handler].acquire(), name="lock")
            done, _ = await aio.wait([t1, t2], return_when=aio.FIRST_COMPLETED)
            # 等待完成后，一定要记得取消另一个任务！否则可能异常加锁
            if done.pop().get_name() == "flag":
                res = cls.__attach(event, handler)
                cls.DEADLOCK_FLAGS[handler].clear()
                t2.cancel()
                return res
            else:
                res = cls.__attach(event, handler)
                cls.WORK_LOCKS[handler].release()
                t1.cancel()
                return res

    @classmethod
    def _hup(cls, session: BotSession) -> None:
        """
        挂起 session
        """
        if session._space_tag is None:
            raise BotSessionError(
                "一次性 session 或空 session 不支持挂起，因为缺乏 session_rule 作为唤醒标志"
            )
        elif session._expired:
            raise BotSessionError("过期的 session 不能被挂起")
        session.hup_times.append(time.time())
        cls.STORAGE[session._space_tag].remove(session)
        cls.HUP_STORAGE[session._space_tag].add(session)
        session._awake_signal.clear()

    @classmethod
    def _rouse(cls, session: BotSession) -> None:
        """
        唤醒 session
        """
        cls.HUP_STORAGE[session._space_tag].remove(session)
        cls.STORAGE[session._space_tag].add(session)
        session._awake_signal.set()

    @classmethod
    def _expire(cls, session: BotSession) -> None:
        """
        标记该 session 为过期状态，并进行销毁操作（如果存在于某个 session_space，则从中移除）
        """
        if session._expired:
            return
        session.events.clear()
        session.hup_times.clear()
        session.store_clear()
        session._expired = True
        if session._space_tag:
            cls.STORAGE[session._space_tag].remove(session)

    @classmethod
    def recycle(cls, session: BotSession, alive: bool = False) -> None:
        """
        session 所在方法运行结束后，回收 session。
        默认将 session 销毁。若 alive 为 True，则保留
        """
        session._free_signal.set()
        if not alive:
            cls._expire(session)

    @classmethod
    async def get(
        cls, event: BotEvent, responder: AbstractResponder, handler: object
    ) -> Optional[BotSession]:
        """
        handler 内获取 session 方法。自动根据 handler._rule 判断是否需要映射到 session_space 进行存储。
        然后根据具体情况，获取已有 session 或新建 session。当尝试获取非空闲 session 时，如果 handler 指定不等待则返回 None
        """
        if handler._rule:
            # session_space, session._free_signal 竞争，需要加锁
            async with cls.WORK_LOCKS[handler]:
                session = await cls._get_on_rule(event, responder, handler)
                # 必须在锁的保护下修改 session._free_signal
                if session:
                    session._free_signal.clear()
        else:
            session = cls._make(event, responder, handler)
            session._free_signal.clear()

        return session

    @classmethod
    def _make(
        cls, event: BotEvent, responder: AbstractResponder, handler: object = None
    ) -> BotSession:
        """
        内部使用的创建 session 方法。如果 handler 为空，即缺乏 space_tag，则为一次性 session。
        或 handler._rule 为空，则也为一次性 session
        """
        if handler:
            if handler._rule:
                session = BotSession(cls, responder, handler)
                session.events.append(event)
                cls.STORAGE[handler].add(session)
                return session
        session = BotSession(cls, responder)
        session.events.append(event)
        return session

    @classmethod
    def make_empty(cls, responder: AbstractResponder) -> BotSession:
        """
        创建空 session。即不含 event 和 space_tag 标记的 session
        """
        return BotSession(cls, responder)

    @classmethod
    def make_temp(cls, event: BotEvent, responder: AbstractResponder) -> BotSession:
        """
        创建一次性 session。确定无需 session 管理机制时可以使用。
        否则一定使用 cls.get 方法
        """
        return cls._make(event, responder)

    @classmethod
    async def _get_on_rule(
        cls, event: BotEvent, responder: AbstractResponder, handler: object
    ) -> Optional[BotSession]:
        """
        根据 handler 具体情况，从对应 session_space 中获取 session 或新建 session。
        或从 hup_session_space 中唤醒 session，或返回 None
        """
        session = None
        check_rule, session_space, hup_session_space, conflict_wait = (
            handler._rule,
            cls.STORAGE[handler],
            cls.HUP_STORAGE[handler],
            handler._wait_flag,
        )

        # for 循环都需要即时 break，保证遍历 session_space 时没有协程切换。因为切换后 session_space 可能发生变动
        for s in session_space:
            if check_rule.compare(s.event, event) and not s._expired:
                session = s
                break
        # 如果会话不存在，生成一个新 session 变量
        if session is None:
            return cls._make(event, responder, handler)
        # 如果会话存在，且未过期，且空闲，则附着到这个 session 上
        if session._free_signal.is_set():
            session.events.append(event)
            return session
        # 如果会话存在，且未过期，但是不空闲，选择不等待
        if not conflict_wait:
            return None
        # 如果会话存在，且未过期，但是不空闲，选择等待，此时就不得不陷入等待（即将发生协程切换）
        await aio.wait(
            [session._free_signal.wait(), session._hup_signal.wait()],
            return_when=aio.FIRST_COMPLETED,
        )
        if session._hup_signal.is_set():
            cls.DEADLOCK_FLAGS[handler].set()
            await session._free_signal.wait()
        """
        重新切换回本协程后，session 有可能变为过期，但此时一定是空闲的。
        同时一定是非挂起状态。因为上面解决了可能存在的挂起死锁问题。
        即使该 session 因过期被所在的 session_space 清除也无妨，因为此处有引用，
        该 session 并不会消失。且此处不操作 session_space，无需担心 session_space 变动
        """
        # 如果过期，生成一个新的 session 变量
        if session._expired:
            return cls._make(event, responder, handler)
        # 如果未过期，则附着到这个 session 上
        else:
            session.events.append(event)
            return session


_session_ctx = ContextVar("session_ctx")


class SessionLocal:
    """
    session 自动上下文
    """

    __slots__ = tuple(
        list(filter(lambda x: not (len(x) >= 2 and x[:2] == "__"), dir(BotSession)))
        + ["__storage__"]
    )

    def __init__(self) -> None:
        object.__setattr__(self, "__storage__", _session_ctx)
        self.__storage__: ContextVar[BotSession]

    def __setattr__(self, __name: str, __value: Any) -> None:
        setattr(self.__storage__.get(), __name, __value)

    def __getattr__(self, __name: str) -> Any:
        return getattr(self.__storage__.get(), __name)

    def _add_ctx(self, ctx: BotSession) -> Token:
        return self.__storage__.set(ctx)

    def _del_ctx(self, token: Token) -> None:
        self.__storage__.reset(token)


class AttrSessionRule(SessionRule):
    def __init__(self, *attrs) -> None:
        super().__init__()
        self.attrs = attrs

    def _get_val(self, e: BotEvent, attrs: Tuple[str, ...]) -> Any:
        val = e
        try:
            for attr in attrs:
                val = getattr(val, attr)
        except AttributeError:
            raise BotSessionError(f"session 规则指定的属性 {attr} 不存在")
        return val

    def compare(self, e1: BotEvent, e2: BotEvent) -> bool:
        return self._get_val(e1, self.attrs) == self._get_val(e2, self.attrs)


SESSION_LOCAL = SessionLocal()
SESSION_LOCAL: BotSession


async def send(
    content: str | CQMsgDict | List[CQMsgDict],
    cq_str: bool = False,
    wait: bool = False,
) -> Optional[ResponseEvent]:
    """
    发送一条消息
    """
    return await SESSION_LOCAL.send(content, cq_str, wait)


async def send_hup(
    content: str | CQMsgDict | List[CQMsgDict],
    cq_str: bool = False,
    overtime: int = None,
) -> None:
    """
    回复一条消息然后挂起
    """
    await SESSION_LOCAL.send(content, cq_str)
    await SESSION_LOCAL.hup(overtime)


async def send_reply(
    content: str | CQMsgDict | List[CQMsgDict],
    cq_str: bool = False,
    wait: bool = False,
) -> Optional[ResponseEvent]:
    """
    发送一条消息（以回复消息的形式，回复触发动作的那条消息）
    """
    content_arr = [reply_msg(SESSION_LOCAL.event.id)]
    if isinstance(content, str):
        content_arr.append(text_msg(content))
    elif isinstance(content, dict):
        content_arr.append(content)
    else:
        content_arr.extend(content)
    return await SESSION_LOCAL.send(content_arr, cq_str, wait)


async def finish(
    content: str | CQMsgDict | List[CQMsgDict], cq_str: bool = False
) -> None:
    """
    回复一条消息，然后直接结束当前事件处理方法
    """
    await SESSION_LOCAL.send(content, cq_str)
    SESSION_LOCAL.destory()
    raise DirectRetSignal("事件处理方法被安全地递归 return，请无视这个异常")


def any_event():
    """
    获取当前 session 上下文下标注为联合类型的 event
    """
    return SESSION_LOCAL.event


def msg_event() -> MessageEvent:
    """
    获取当前 session 上下文下的 MessageEvent
    """
    return SESSION_LOCAL.event


def notice_event() -> NoticeEvent:
    """
    获取当前 session 上下文下的 NoticeEvent
    """
    return SESSION_LOCAL.event


def req_evnt() -> RequestEvent:
    """
    获取当前 session 上下文下的 RequestEvent
    """
    return SESSION_LOCAL.event


def meta_event() -> MetaEvent:
    """
    获取当前 session 上下文下的 MetaEvent
    """
    return SESSION_LOCAL.event


def msg_text():
    """
    获取当前 session 上下文下的 event.text，如果不存在则返回 None
    """
    if hasattr(SESSION_LOCAL.event, "text"):
        return SESSION_LOCAL.event.text
    return None
