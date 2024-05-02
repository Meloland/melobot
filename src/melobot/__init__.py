"""MeloBot 是插件化管理、基于异步会话机制的机器人开发框架。

v2 版本目前仅适用于构建与 OneBot 实现对接的机器人服务。

项目源码和文档，请参考：https://github.com/Meloland/melobot
"""

from .base import (
    LogicMode,
    PriorLevel,
    SessionRule,
    User,
    lock,
    semaphore,
    this_dir,
    timelimit,
)
from .bot import MeloBot, thisbot
from .context import (
    SessionOption,
    finish,
    msg_args,
    msg_event,
    msg_text,
    pause,
    reply_finish,
    send,
    send_reply,
    send_wait,
    session_store,
)
from .io import ForwardWsConn, HttpConn, ReverseWsConn
from .meta import MetaInfo
from .plugin import BotPlugin
from .utils import (
    CmdArgFormatter,
    CmdParser,
    GroupMsgLvlChecker,
    MsgChecker,
    NoticeChecker,
    PrivateMsgLvlChecker,
    ReqChecker,
)

__version__ = MetaInfo.VER
