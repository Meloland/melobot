from ..ctx import LoggerCtx as _LoggerCtx
from .base import GenericLogger, Logger, LogLevel
from .patch import LazyLogMethod, LoguruPatch, StandardPatch, StructlogPatch, logger_patch


def get_logger() -> GenericLogger:
    return _LoggerCtx().get()
