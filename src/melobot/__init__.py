from typing_extensions import TYPE_CHECKING

# 让 melobot 启用内置异常格式化器
from . import _render
from ._lazy import lazy_import as _lazy_import
from ._lazy import lazy_load

# TODO: 考虑在最低支持 3.11 后，使用 asyncio.TaskGroup 替代多数任务生成场景

if TYPE_CHECKING:
    from ._meta import MetaInfo, __version__
    from ._render import install_exc_hook, set_traceback_style, uninstall_exc_hook
    from .adapter import Action, Adapter, Echo, Event
    from .adapter.generic import send_image, send_text
    from .bot import Bot, get_bot
    from .ctx import Context
    from .di import Depends, Exclude, MatchEvent, Reflect, inject_deps
    from .handle import (
        Flow,
        FlowDecorator,
        FlowNode,
        FlowStore,
        block,
        bypass,
        flow_to,
        get_event,
        get_flow_arg,
        get_flow_store,
        nextn,
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
        try_get_event,
    )
    from .log import GenericLogger, Logger, get_logger
    from .plugin import AsyncShare, PluginInfo, PluginLifeSpan, PluginPlanner, SyncShare
    from .session import (
        DefaultRule,
        Rule,
        Session,
        SessionStore,
        enter_session,
        get_session,
        get_session_arg,
        get_session_store,
        suspend,
    )
    from .typ._enum import Color, LogicMode, LogLevel
else:
    _lazy_import(
        globals(),
        map={
            "._meta": ("MetaInfo", "__version__"),
            "._render": ("install_exc_hook", "set_traceback_style", "uninstall_exc_hook"),
            ".adapter": ("Action", "Adapter", "Echo", "Event"),
            ".adapter.generic": ("send_image", "send_text"),
            ".bot": ("Bot", "get_bot"),
            ".ctx": ("Context",),
            ".di": ("Depends", "Exclude", "MatchEvent", "Reflect", "inject_deps"),
            ".handle": (
                "Flow",
                "FlowDecorator",
                "FlowNode",
                "FlowStore",
                "block",
                "bypass",
                "flow_to",
                "get_event",
                "get_flow_arg",
                "get_flow_store",
                "nextn",
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
                "try_get_event",
            ),
            ".log": ("GenericLogger", "Logger", "get_logger"),
            ".plugin": ("AsyncShare", "PluginInfo", "PluginLifeSpan", "PluginPlanner", "SyncShare"),
            ".session": (
                "DefaultRule",
                "Rule",
                "Session",
                "SessionStore",
                "enter_session",
                "get_session",
                "get_session_arg",
                "get_session_store",
                "suspend",
            ),
            ".typ._enum": ("Color", "LogicMode", "LogLevel"),
        },
        deprecations={},
    )
# 让 melobot 开始接管导入机制
from ._imp import ALL_EXTS as MODULE_EXTS
from ._imp import add_import_fallback
