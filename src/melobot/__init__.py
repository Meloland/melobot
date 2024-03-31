"""MeloBot 是插件化管理、基于异步会话机制的 qq 机器人开发框架。

项目源码和文档，请参考：https://github.com/aicorein/melobot
"""

from .base import (
    LogicMode,
    PriorLevel,
    SessionRule,
    User,
    cooldown,
    lock,
    this_dir,
    timelimit,
)
from .bot import MeloBot, thisbot
from .context import (
    AttrSessionRule,
    finish,
    get_store,
    msg_args,
    msg_event,
    msg_text,
    pause,
    reply_finish,
    send,
    send_reply,
    send_wait,
)
from .io import ForwardWsConn, HttpConn, ReverseWsConn
from .meta import MetaInfo
from .plugin import BotPlugin
from .utils import (
    ArgFormatter,
    AtChecker,
    CmdParser,
    CmdParserGen,
    GroupMsgLvlChecker,
    MsgCheckerGen,
    PrivateMsgLvlChecker,
)

__version__ = MetaInfo().VER
