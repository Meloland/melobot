import re
import sys
import types
from typing import Any, Callable, Protocol, cast

from .base import GenericLogger, Logger, LogLevel


class LazyLogMethod(Protocol):
    def __call__(
        self,
        msg: str,
        *arg_getters: Callable[[], Any],
        level: LogLevel,
        with_exc: bool = False,
    ) -> None:
        raise NotImplementedError


def logger_patch(logger: Any, lazy_meth: LazyLogMethod) -> GenericLogger:
    setattr(logger, Logger.generic_lazy.__name__, lazy_meth)
    setattr(
        logger, Logger.generic_obj.__name__, types.MethodType(Logger.generic_obj, logger)
    )
    return cast(GenericLogger, logger)


class StandardPatch(LazyLogMethod):
    def __init__(self, logger: Any) -> None:
        super().__init__()
        self.logger = logger

    def __call__(
        self,
        msg: str,
        *arg_getters: Callable[[], Any],
        level: LogLevel,
        with_exc: bool = False,
    ) -> None:
        if not self.logger.isEnabledFor(level):
            return
        exc = sys.exc_info() if with_exc else None
        self.logger._log(level, msg, tuple(g() for g in arg_getters), exc_info=exc)


class LoguruPatch(LazyLogMethod):
    def __init__(self, logger: Any) -> None:
        super().__init__()
        self.logger = logger
        self.pattern = re.compile(r"%(?:[-+# 0]*\d*(?:\.\d+)?[hlL]?[diouxXeEfFgGcrs%])")

    def __call__(
        self,
        msg: str,
        *arg_getters: Callable[[], Any],
        level: LogLevel,
        with_exc: bool = False,
    ) -> None:
        logger = self.logger.opt(lazy=True)
        msg = self.pattern.sub("{}", msg)

        if with_exc:
            logger.exception(msg, *arg_getters)
            return

        match level:
            case LogLevel.DEBUG:
                logger.debug(msg, *arg_getters)
            case LogLevel.INFO:
                logger.info(msg, *arg_getters)
            case LogLevel.WARNING:
                logger.warning(msg, *arg_getters)
            case LogLevel.ERROR:
                logger.error(msg, *arg_getters)
            case LogLevel.CRITICAL:
                logger.critical(msg, *arg_getters)
            case _:
                raise ValueError(f"无效的日志等级：{level}")


class StructlogPatch(LazyLogMethod):
    def __init__(self, logger: Any) -> None:
        super().__init__()
        self.logger = logger

    def __call__(
        self,
        msg: str,
        *arg_getters: Callable[[], Any],
        level: LogLevel,
        with_exc: bool = False,
    ) -> None:
        args = tuple(g() for g in arg_getters)
        logger = self.logger
        if with_exc:
            logger.exception(msg, *args)
            return

        match level:
            case LogLevel.DEBUG:
                logger.debug(msg, *args)
            case LogLevel.INFO:
                logger.info(msg, *args)
            case LogLevel.WARNING:
                logger.warning(msg, *args)
            case LogLevel.ERROR:
                logger.error(msg, *args)
            case LogLevel.CRITICAL:
                logger.critical(msg, *args)
            case _:
                raise ValueError(f"无效的日志等级：{level}")
