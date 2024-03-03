"""
MeloBot 是插件化管理、基于异步会话机制的 qbot 开发框架。

项目源码和文档，请参考：https://github.com/AiCorein/Qbot-MeloBot
"""

from .core.init import MeloBot
from .meta import META_INFO, MetaInfo
from .models.action import *
from .models.base import ID_WORKER, RWController, get_twin_event
from .models.bot import BOT_PROXY as bot
from .models.event import MetaEvent, MsgEvent, NoticeEvent, RequestEvent, RespEvent
from .models.ipc import PluginBus, PluginStore
from .models.plugin import Plugin
from .models.session import SESSION_LOCAL as session
from .models.session import (
    AttrSessionRule,
    BotSession,
    finish,
    send,
    send_hup,
    send_reply,
)
from .types.exceptions import BotException, BotHupTimeout
from .types.models import BotEvent, BotLife, SessionRule, ShareObjArgs
from .types.typing import Callable, PriorityLevel, User
from .types.utils import BotChecker, BotMatcher
from .utils.base import clear_cq, cooldown, lock, semaphore, this_dir
from .utils.checker import GroupMsgLvl, MsgCheckerGen, MsgLvlChecker, PrivateMsgLvl
from .utils.formatter import ArgFormatter
from .utils.matcher import (
    AlwaysMatch,
    ContainMatch,
    EndMatch,
    FullMatch,
    RegexMatch,
    StartMatch,
)
from .utils.parser import CmdParser, CmdParserGen

session: BotSession


def get_metainfo() -> MetaInfo:
    """
    获取 melobot 核心元信息，外部更改无效
    """
    return MetaInfo()


def get_id() -> int:
    """
    获取一个全局唯一 id，由 melobot 内部 id 生成器提供
    """
    return ID_WORKER.get_id()


def get_event():
    """
    获得当前 session 下活动的 event
    """
    return session.event


async def make_async(func: Callable):
    """
    异步包装器，将一个同步函数包装为异步函数。保留返回值。
    如果需要传参使用 partial 包裹
    """

    async def wrapper():
        return func()

    return wrapper


async def make_coro(func: Callable):
    """
    协程包装器，将一个同步函数包装为协程。保留返回值。
    如果需要传参使用 partial 包裹
    """

    async def wrapper():
        return func()

    return wrapper()


__version__ = META_INFO.VER
__all__ = (
    "MeloBot",
    "BotException",
    "BotHupTimeout",
    "bot",
    "BotEvent",
    "BotLife",
    "ShareObjArgs",
    "User",
    "PriorityLevel",
    "get_metainfo",
    "BotChecker",
    "BotMatcher",
    "RWController",
    "this_dir",
    "clear_cq",
    "lock",
    "semaphore",
    "cooldown",
    "get_twin_event",
    "get_id",
    "get_event",
    "make_async",
    "make_coro",
    "MsgEvent",
    "RequestEvent",
    "NoticeEvent",
    "MetaEvent",
    "RespEvent",
    "Plugin",
    "PluginStore",
    "PluginBus",
    "session",
    "SessionRule",
    "AttrSessionRule",
    "send",
    "send_hup",
    "send_reply",
    "finish",
    "MsgLvlChecker",
    "GroupMsgLvl",
    "PrivateMsgLvl",
    "MsgCheckerGen",
    "StartMatch",
    "AlwaysMatch",
    "ContainMatch",
    "EndMatch",
    "FullMatch",
    "RegexMatch",
    "CmdParser",
    "CmdParserGen",
    "ArgFormatter",
    # action 部分
    "text_msg",
    "face_msg",
    "audio_msg",
    "at_msg",
    "share_msg",
    "music_msg",
    "custom_music_msg",
    "image_msg",
    "reply_msg",
    "poke_msg",
    "tts_msg",
    "cq_escape",
    "cq_anti_escape",
    "to_cq_str_format",
)
