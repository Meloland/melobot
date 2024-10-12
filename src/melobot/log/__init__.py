from ..ctx import LoggerCtx as _LoggerCtx
from .base import GenericLogger, Logger, LogLevel
from .patch import LazyLogMethod, LoguruPatch, StandardPatch, StructlogPatch, logger_patch


def get_logger() -> GenericLogger:
    """获取当前上下文中日志器

    :return: 日志器
    """
    return _LoggerCtx().get()
