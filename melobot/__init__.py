from .core.init import MeloBot
from .core.proxy import BOT_PROXY as bot

from .interface.exceptions import BotException
from .interface.models import BotEvent, ShareObjArgs
from .interface.typing import UserLevel, PriorityLevel, METAINFO as meta_info
from .interface.utils import BotChecker, BotMatcher, BotParser

from .models.base import RWController, AsyncTwinEvent, ID_WORKER as id_worker
from .models.event import MsgEvent, RequestEvent, NoticeEvent, MetaEvent, RespEvent
from .models.plugin import Plugin
from .models.ipc import PluginStore, PluginBus, SignalSource, SIGNAL_SOURCE_LOCAL as signal_source
signal_source: SignalSource
from .models.session import BotSession, SESSION_LOCAL as session
session: BotSession

from .utils.checker import MsgAccessChecker
from .utils.matcher import StartMatcher, ContainMatcher, EndMatcher, FullMatcher, RegexMatcher
from .utils.parser import CmdParser


__version__ = meta_info.VER
__all__ = (
    "MeloBot",
    "bot",
    "BotException",
    "BotEvent",
    "ShareObjArgs",
    "UserLevel",
    "PriorityLevel",
    "meta_info",
    "BotChecker",
    "BotMatcher",
    "BotParser",
    "RWController",
    "AsyncTwinEvent",
    "id_worker",
    "MsgEvent",
    "RequestEvent",
    "NoticeEvent",
    "MetaEvent",
    "RespEvent",
    "Plugin",
    "PluginStore",
    "PluginBus",
    "signal_source",
    "session",
    "MsgAccessChecker",
    "StartMatcher",
    "ContainMatcher",
    "EndMatcher",
    "FullMatcher",
    "RegexMatcher",
    "CmdParser"
)