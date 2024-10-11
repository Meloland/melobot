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
        """懒惰日志抽象方法

        继承并实现该类的 __call__ 方法，即可用于日志器修补

        :param msg: 日志消息
        :param level: 日志等级
        :param with_exc: 输出时是否附加异常信息
        """
        raise NotImplementedError


def logger_patch(logger: Any, lazy_meth: LazyLogMethod) -> GenericLogger:
    """对指定的日志器进行修补操作，使其可以被用于 melobot 内部的日志记录

    :param logger: 任意已经实现 `debug`, `info`, `warning`, `error`, `critical`, `exception` 接口的日志器
    :param lazy_meth: 修补方法
    """
    setattr(logger, Logger.generic_lazy.__name__, lazy_meth)
    setattr(
        logger, Logger.generic_obj.__name__, types.MethodType(Logger.generic_obj, logger)
    )
    return cast(GenericLogger, logger)


class StandardPatch(LazyLogMethod):
    """用于修补 logging.Logger 的日志修补"""

    def __init__(self, logger: Any) -> None:
        """初始化一个标准日志器修补

        :param logger: 标准日志器对象（`logging.Logger`）
        """
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
    """用于修补 loguru 日志器的日志修补"""

    def __init__(self, logger: Any) -> None:
        """初始化一个 loguru 日志器修补

        :param logger: loguru 日志器对象
        """
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
    """用于修补 structlog 日志器的日志修补"""

    def __init__(self, logger: Any) -> None:
        """初始化一个 structlog 日志器修补

        :param logger: structlog 日志器对象
        """
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
