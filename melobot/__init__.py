"""
MeloBot 是插件化管理、基于异步会话机制的 qbot 开发框架。

项目源码和文档，请参考：https://github.com/aicorein/melobot
"""

from .core.init import MeloBot
from .meta import META_INFO, MetaInfo
from .models import (
    AttrSessionRule,
    BotSession,
    MetaEvent,
    MsgEvent,
    NoticeEvent,
    Plugin,
    PluginBus,
    PluginStore,
    RequestEvent,
    RespEvent,
    RWController,
    bot,
    finish,
    get_twin_event,
    send,
    send_hup,
    send_reply,
    session,
)
from .types import (
    BotChecker,
    BotEvent,
    BotLife,
    BotMatcher,
    PriorityLevel,
    SessionRule,
    ShareObjArgs,
    User,
)
from .utils import (
    AlwaysMatch,
    ArgFormatter,
    CmdParser,
    CmdParserGen,
    ContainMatch,
    EndMatch,
    FullMatch,
    GroupMsgLvl,
    MsgCheckerGen,
    MsgLvlChecker,
    PrivateMsgLvl,
    RegexMatch,
    StartMatch,
    clear_cq,
    cooldown,
    get_id,
    lock,
    semaphore,
    this_dir,
    to_async,
    to_coro,
)

session: BotSession


def get_metainfo() -> MetaInfo:
    """
    获取 melobot 核心元信息，外部更改无效
    """
    return MetaInfo()


__version__ = META_INFO.VER
__all__ = (
    "MeloBot",
    "get_metainfo",
    "AttrSessionRule",
    "session",
    "MetaEvent",
    "MsgEvent",
    "NoticeEvent",
    "Plugin",
    "PluginBus",
    "PluginStore",
    "RequestEvent",
    "RespEvent",
    "RWController",
    "bot",
    "finish",
    "get_twin_event",
    "send",
    "send_hup",
    "send_reply",
    "BotChecker",
    "BotEvent",
    "BotLife",
    "BotMatcher",
    "PriorityLevel",
    "SessionRule",
    "ShareObjArgs",
    "User",
    "AlwaysMatch",
    "ArgFormatter",
    "CmdParser",
    "CmdParserGen",
    "ContainMatch",
    "EndMatch",
    "FullMatch",
    "GroupMsgLvl",
    "MsgCheckerGen",
    "MsgLvlChecker",
    "PrivateMsgLvl",
    "RegexMatch",
    "StartMatch",
    "clear_cq",
    "cooldown",
    "get_id",
    "lock",
    "semaphore",
    "this_dir",
    "to_async",
    "to_coro",
)
