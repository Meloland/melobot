from typing_extensions import Any

from ..ctx import LoggerCtx as _LoggerCtx
from .base import GenericLogger, Logger, LogLevel
from .patch import LazyLogMethod, LoguruPatch, StandardPatch, StructlogPatch, logger_patch


def get_logger() -> GenericLogger:
    """获取当前上下文中日志器

    :return: 日志器
    """
    return _LoggerCtx().get()


def __getattr__(name: str) -> Any:
    if name == "logger":
        return get_logger()
    else:
        raise AttributeError


logger: GenericLogger
"""当前上下文中的日志器"""
