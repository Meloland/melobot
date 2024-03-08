import logging
import logging.config
import logging.handlers
import os
from collections.abc import Mapping
from logging import CRITICAL, DEBUG, ERROR, INFO, WARN, WARNING, Logger
from types import TracebackType

from ..types.typing import *


def get_logger(
    log_dir: str = None,
    log_level: Literal[
        "DEBUG", "ERROR", "INFO", "WARN", "WARNING", "CRITICAL"
    ] = "DEBUG",
) -> Logger:
    """
    无日志目录时获取只含 console 输出的 logger，否则返回含文件输出的 logger
    """
    if log_dir:
        if not os.path.exists(log_dir):
            os.mkdir(log_dir)
        config = get_config(log_dir, log_level)
    else:
        config = get_fileless_config(log_level)
    logging.config.dictConfig(config)
    return logging.getLogger("bot_logger")


def get_fileless_config(log_level: str):
    """
    返回只含 console 输出的 logger
    """
    config = LOG_CONFIG.copy()
    config["handlers"]["console_handler"]["level"] = LOG_LEVEL_MAP[log_level]
    return config


def get_config(log_dir: str, log_level: str):
    """
    返回含 console 输出和文件输出的 logger
    """
    config = LOG_CONFIG.copy()
    config["handlers"]["console_handler"]["level"] = LOG_LEVEL_MAP[log_level]
    config["handlers"]["file_handler"] = {
        "class": "logging.handlers.RotatingFileHandler",
        "level": logging.DEBUG,
        "formatter": "file_formatter",
        "filename": os.path.join(log_dir, "bot.log"),
        "maxBytes": 1024 * 1024,
        "backupCount": 10,
        "encoding": "UTF-8",
    }
    config["loggers"]["bot_logger"]["handlers"].append("file_handler")
    return config


LOG_COLOR_CONFIG = {
    "DEBUG": "purple",
    "INFO": "white",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "bold_red",
}


LOG_LEVEL_MAP = {
    "DEBUG": DEBUG,
    "INFO": INFO,
    "WARN": WARN,
    "WARNING": WARNING,
    "ERROR": ERROR,
    "CRITICAL": CRITICAL,
}


LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": True,
    "incremental": False,
    "formatters": {
        "console_formatter": {
            "()": "colorlog.ColoredFormatter",
            "format": "%(log_color)s[%(asctime)s] [%(levelname)s]: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
            "log_colors": LOG_COLOR_CONFIG,
        },
        "file_formatter": {
            "class": "logging.Formatter",
            "format": "[%(asctime)s] [%(filename)s %(lineno)d] [%(levelname)s]: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console_handler": {
            "class": "logging.StreamHandler",
            "level": logging.INFO,
            "formatter": "console_formatter",
        }
    },
    "loggers": {
        "bot_logger": {
            "handlers": ["console_handler"],
            "level": logging.DEBUG,
            "propagate": False,
        }
    },
}


_SysExcInfoType: TypeAlias = (
    Tuple[Type[BaseException], BaseException, Optional[TracebackType]]
    | Tuple[None, None, None]
)
_ExcInfoType: TypeAlias = None | bool | _SysExcInfoType | BaseException


class PrefixLogger:
    """
    二次包装的日志器
    """

    def __init__(self, ref: Logger, prefix: str) -> None:
        self._logger = ref
        self._prefix = prefix

    def _add_prefix(self, s: str) -> str:
        return f"[{self._prefix}] {s}"

    def info(
        self,
        msg: object,
        *args: object,
        exc_info: _ExcInfoType = None,
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Optional[Mapping[str, object]] = None,
    ) -> None:
        msg = self._add_prefix(msg)
        return self._logger.info(
            msg,
            *args,
            exc_info=exc_info,
            stack_info=stack_info,
            stacklevel=stacklevel,
            extra=extra,
        )

    def warn(
        self,
        msg: object,
        *args: object,
        exc_info: _ExcInfoType = None,
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Optional[Mapping[str, object]] = None,
    ) -> None:
        msg = self._add_prefix(msg)
        return self._logger.warn(
            msg,
            *args,
            exc_info=exc_info,
            stack_info=stack_info,
            stacklevel=stacklevel,
            extra=extra,
        )

    def warning(
        self,
        msg: object,
        *args: object,
        exc_info: _ExcInfoType = None,
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Optional[Mapping[str, object]] = None,
    ) -> None:
        msg = self._add_prefix(msg)
        return self._logger.warning(
            msg,
            *args,
            exc_info=exc_info,
            stack_info=stack_info,
            stacklevel=stacklevel,
            extra=extra,
        )

    def error(
        self,
        msg: object,
        *args: object,
        exc_info: _ExcInfoType = None,
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Optional[Mapping[str, object]] = None,
    ) -> None:
        msg = self._add_prefix(msg)
        return self._logger.error(
            msg,
            *args,
            exc_info=exc_info,
            stack_info=stack_info,
            stacklevel=stacklevel,
            extra=extra,
        )

    def debug(
        self,
        msg: object,
        *args: object,
        exc_info: _ExcInfoType = None,
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Optional[Mapping[str, object]] = None,
    ) -> None:
        msg = self._add_prefix(msg)
        return self._logger.debug(
            msg,
            *args,
            exc_info=exc_info,
            stack_info=stack_info,
            stacklevel=stacklevel,
            extra=extra,
        )

    def critical(
        self,
        msg: object,
        *args: object,
        exc_info: _ExcInfoType = None,
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Optional[Mapping[str, object]] = None,
    ) -> None:
        msg = self._add_prefix(msg)
        return self._logger.critical(
            msg,
            *args,
            exc_info=exc_info,
            stack_info=stack_info,
            stacklevel=stacklevel,
            extra=extra,
        )
