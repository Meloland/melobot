from .core.init import MeloBot

from .interface.exceptions import BotException
from .interface.models import BotEvent, BotLife, ShareObjArgs
from .interface.typing import UserLevel, PriorityLevel, MetaInfo, METAINFO
from .interface.utils import BotChecker, BotMatcher, BotParser

from .models.bot import BOT_PROXY as bot
from .models.base import RWController, get_twin_event, ID_WORKER
from .models.event import MsgEvent, RequestEvent, NoticeEvent, MetaEvent, RespEvent
from .models.plugin import Plugin
from .models.ipc import PluginStore, PluginBus
from .models.session import BotSession, SESSION_LOCAL as session
session: BotSession

from .utils.checker import MsgAccessChecker
from .utils.matcher import StartMatcher, ContainMatcher, EndMatcher, FullMatcher, RegexMatcher
from .utils.parser import CmdParser


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
    "BotException",
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
    "MsgAccessChecker",
    "StartMatcher",
    "ContainMatcher",
    "EndMatcher",
    "FullMatcher",
    "RegexMatcher",
    "CmdParser"
)