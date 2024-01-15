from .core.init import MeloBot
from .interface.models import BotEvent, BotLife, ShareObjArgs
from .interface.typing import METAINFO, Callable, MetaInfo, PriorityLevel, User
from .interface.utils import BotChecker, BotMatcher
from .models.base import ID_WORKER, RWController, get_twin_event, in_cwd
from .models.bot import BOT_PROXY as bot
from .models.event import (MetaEvent, MsgEvent, NoticeEvent, RequestEvent,
                           RespEvent)
from .models.ipc import PluginBus, PluginStore
from .models.plugin import Plugin
from .models.session import SESSION_LOCAL as session
from .models.session import (AttrSessionRule, BotSession, SessionRule, finish,
                             reply, reply_hup)
from .utils.checker import GroupMsgLvl, MsgLvlChecker, PrivateMsgLvl
from .utils.matcher import (ContainMatch, EndMatch, FullMatch, RegexMatch,
                            StartMatch)
from .utils.parser import CmdParser

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


__version__ = METAINFO.VER
__all__ = (
    "MeloBot",
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
    "in_cwd",
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
    "reply",
    "reply_hup",
    "finish",
    "MsgLvlChecker",
    "GroupMsgLvl",
    "PrivateMsgLvl",
    "StartMatch",
    "ContainMatch",
    "EndMatch",
    "FullMatch",
    "RegexMatch",
    "CmdParser"
)