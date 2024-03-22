import logging
import logging.config
import logging.handlers
import os
from collections.abc import Mapping
from logging import CRITICAL, DEBUG, ERROR, INFO, WARNING, Logger
from types import TracebackType

import coloredlogs

from ..base.exceptions import DuplicateError
from ..base.typing import Literal, Optional, Type, TypeAlias


class NullLogger(Logger):
    """获得一个空日志器，支持所有日志操作， 但是丢弃所有日志."""

    def __init__(self, name: str) -> None:
        super().__init__(name, CRITICAL)
        self.addHandler(logging.NullHandler())


class BotLogger(Logger):
    LOGGERS: dict[str, "BotLogger"] = {}

    FIELD_COLORS = {
        "asctime": {"color": "white"},
        "hostname": {"color": "magenta"},
        "levelname": {"bold": True, "color": "white"},
        "name": {"color": "blue"},
        "programname": {"color": "cyan"},
        "username": {"color": "yellow"},
    }

    LEVEL_COLORS = {
        "critical": {"bold": True, "color": "red"},
        "debug": {"color": "magenta"},
        "error": {"color": "red"},
        "info": {},
        "notice": {"color": "magenta"},
        "spam": {"color": "green", "faint": True},
        "success": {"bold": True, "color": "green"},
        "verbose": {"color": "blue"},
        "warning": {"color": "yellow"},
    }

    LEVEL_MAP = {
        "DEBUG": DEBUG,
        "INFO": INFO,
        "WARNING": WARNING,
        "ERROR": ERROR,
        "CRITICAL": CRITICAL,
    }

    @staticmethod
    def _console_fmt(name: str, no_tag: bool = False) -> logging.Formatter:
        fmt_s = (
            f"[%(asctime)s] [%(levelname)s] [{name}] %(message)s"
            if not no_tag
            else "[%(asctime)s] [%(levelname)s] %(message)s"
        )
        fmt = coloredlogs.ColoredFormatter(
            fmt=fmt_s,
            datefmt="%Y-%m-%d %H:%M:%S",
            level_styles=BotLogger.LEVEL_COLORS,
            field_styles=BotLogger.FIELD_COLORS,
        )
        return fmt

    @staticmethod
    def _console_handler(fmt: logging.Formatter) -> logging.Handler:
        handler = logging.StreamHandler()
        handler.setFormatter(fmt)
        return handler

    @staticmethod
    def _file_fmt(name: str, no_tag: bool = False) -> logging.Formatter:
        fmt_s = (
            f"[%(asctime)s] [%(filename)s %(lineno)d] [%(levelname)s] [{name}] %(message)s"
            if not no_tag
            else "[%(asctime)s] [%(filename)s %(lineno)d] [%(levelname)s] %(message)s"
        )
        fmt = logging.Formatter(
            fmt=fmt_s,
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        return fmt

    @staticmethod
    def _file_handler(
        fmt: logging.Formatter, log_dir: str, name: str
    ) -> logging.Handler:
        if not os.path.exists(log_dir):
            os.mkdir(log_dir)
        handler = logging.handlers.RotatingFileHandler(
            filename=os.path.join(log_dir, f"{name}.log"),
            maxBytes=1024 * 1024,
            backupCount=10,
            encoding="UTF-8",
        )
        handler.setFormatter(fmt)
        return handler

    def __init__(
        self,
        name: str,
        level: Literal["DEBUG", "ERROR", "INFO", "WARNING", "CRITICAL"] = "INFO",
        to_console: bool = True,
        to_dir: Optional[str] = None,
        no_tag: bool = False,
    ) -> None:

        if name in BotLogger.LOGGERS.keys():
            raise DuplicateError(f"名为 {name} 的日志器已存在，请修改 name")
        super().__init__(name, BotLogger.LEVEL_MAP[level])
        BotLogger.LOGGERS[name] = self
        self._con_handler: Optional[logging.Handler] = None
        self._no_tag = no_tag

        if to_console:
            self._add_console_handler()
        if to_dir is not None:
            self._add_file_handler(to_dir)

    def _add_console_handler(self) -> None:
        if self._con_handler is None:
            self._con_handler = self._console_handler(
                self._console_fmt(self.name, self._no_tag)
            )
            self.addHandler(self._con_handler)

    def _add_file_handler(self, log_dir: str) -> None:
        handler = self._file_handler(
            self._file_fmt(self.name, self._no_tag), log_dir, self.name
        )
        self.addHandler(handler)

    def set_level(
        self, level: Literal["DEBUG", "ERROR", "INFO", "WARNING", "CRITICAL"]
    ) -> None:
        self.setLevel(BotLogger.LEVEL_MAP[level])

    def to_console(self) -> None:
        self._add_console_handler()

    def to_dir(self, log_dir: str) -> None:
        self._add_file_handler(log_dir)


_SysExcInfoType: TypeAlias = (
    tuple[Type[BaseException], BaseException, Optional[TracebackType]]
    | tuple[None, None, None]
)
_ExcInfoType: TypeAlias = None | bool | _SysExcInfoType | BaseException


class PrefixLogger:
    """二次包装的日志器."""

    def __init__(self, ref: BotLogger, prefix: str) -> None:
        self._logger = ref
        self._prefix = prefix

    def _add_prefix(self, s: object) -> str:
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
