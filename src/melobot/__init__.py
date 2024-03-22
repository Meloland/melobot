"""MeloBot 是插件化管理、基于异步会话机制的 qbot 开发框架。

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
    any_event,
    finish,
    get_store,
    meta_event,
    msg_args,
    msg_event,
    msg_text,
    notice_event,
    pause,
    reply_finish,
    req_evnt,
    send,
    send_reply,
    send_wait,
)
from .io import ForwardWsConn
from .meta import MetaInfo
from .plugin import BotPlugin
from .utils import (
    ArgFormatter,
    AtChecker,
    CmdParser,
    CmdParserGen,
    ContainMatch,
    EndMatch,
    FullMatch,
    GroupMsgLvl,
    MsgCheckerGen,
    PrivateMsgLvl,
    RegexMatch,
    StartMatch,
)

__version__ = MetaInfo().VER
