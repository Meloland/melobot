from .core.init import MeloBot
from .interface.models import BotEvent, BotLife, ShareObjArgs
from .interface.typing import METAINFO, MetaInfo, PriorityLevel, UserLevel
from .interface.utils import BotChecker, BotMatcher, BotParser
from .models.base import ID_WORKER, RWController, get_twin_event
from .models.bot import BOT_PROXY as bot
from .models.event import (MetaEvent, MsgEvent, NoticeEvent, RequestEvent,
                           RespEvent)
from .models.ipc import PluginBus, PluginStore
from .models.plugin import Plugin
from .models.session import SESSION_LOCAL as session
from .models.session import (AttrSessionRule, BotSession, SessionRule, finish,
                             reply, reply_hup)
from .utils.checker import MsgAccessChecker
from .utils.matcher import (ContainMatcher, EndMatcher, FullMatcher,
                            RegexMatcher, StartMatcher)
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


__version__ = METAINFO.VER
__all__ = (
    "MeloBot",
    "bot",
    "BotEvent",
    "BotLife",
    "ShareObjArgs",
    "UserLevel",
    "PriorityLevel",
    "get_metainfo",
    "BotChecker",
    "BotMatcher",
    "BotParser",
    "RWController",
    "get_twin_event",
    "get_id",
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
    "MsgAccessChecker",
    "StartMatcher",
    "ContainMatcher",
    "EndMatcher",
    "FullMatcher",
    "RegexMatcher",
    "CmdParser"
)