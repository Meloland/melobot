from typing_extensions import Any

# 兼容老版本的导入
from ..typ._enum import LogLevel
from .base import GenericLogger, Logger, NullLogger
from .patch import LazyLogMethod, LoguruPatch, StandardPatch, StructlogPatch, logger_patch
from .reflect import reflect_logger as _reflect_logger
from .reflect import set_global_logger, set_module_logger
from .report import log_exc


def get_logger() -> GenericLogger:
    """获取当前域下可用的日志器

    :return: 日志器
    """
    return _reflect_logger()


def __getattr__(name: str) -> Any:
    if name == "logger":
        return _reflect_logger()
    else:
        raise AttributeError


logger: GenericLogger
"""当前上下文中的日志器"""
