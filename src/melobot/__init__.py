from typing_extensions import TYPE_CHECKING

# 让 melobot 启用内置异常格式化器
from . import _render
from ._lazy import lazy_import as _lazy_import

# TODO: 考虑在最低支持 3.11 后，使用 asyncio.TaskGroup 替代多数任务生成场景

if TYPE_CHECKING:
    from ._meta import MetaInfo, __version__
    from ._render import install_exc_hook, set_traceback_style, uninstall_exc_hook
    from ._run import report_exc
    from .adapter import Action, Adapter, Echo, Event
    from .adapter.generic import send_image, send_text
    from .bot import Bot, get_bot
    from .ctx import Context
    from .di import Depends
    from .handle import (
        Flow,
        FlowDecorator,
        FlowStore,
        node,
        on_command,
        on_contain_match,
        on_end_match,
        on_event,
        on_full_match,
        on_regex_match,
        on_start_match,
        on_text,
        rewind,
        stop,
    )
    from .log import GenericLogger, Logger, LogLevel, get_logger
    from .plugin import AsyncShare, PluginInfo, PluginLifeSpan, PluginPlanner, SyncShare
    from .session import DefaultRule, Rule, Session, SessionStore, enter_session, suspend
    from .typ._enum import LogicMode
else:
    _lazy_import(
        globals(),
        map={
            "._meta": ("MetaInfo", "__version__"),
            "._render": ("install_exc_hook", "set_traceback_style", "uninstall_exc_hook"),
            "._run": ("report_exc",),
            ".adapter": ("Action", "Adapter", "Echo", "Event"),
            ".adapter.generic": ("send_image", "send_text"),
            ".bot": ("Bot", "get_bot"),
            ".ctx": ("Context",),
            ".di": ("Depends",),
            ".handle": (
                "Flow",
                "FlowDecorator",
                "FlowStore",
                "node",
                "on_command",
                "on_contain_match",
                "on_end_match",
                "on_event",
                "on_full_match",
                "on_regex_match",
                "on_start_match",
                "on_text",
                "rewind",
                "stop",
            ),
            ".log": ("GenericLogger", "Logger", "LogLevel", "get_logger"),
            ".plugin": ("AsyncShare", "PluginInfo", "PluginLifeSpan", "PluginPlanner", "SyncShare"),
            ".session": (
                "DefaultRule",
                "Rule",
                "Session",
                "SessionStore",
                "enter_session",
                "suspend",
            ),
            ".typ._enum": ("LogicMode",),
        },
        deprecations={},
    )
# 让 melobot 开始接管导入机制
from ._imp import add_import_fallback
