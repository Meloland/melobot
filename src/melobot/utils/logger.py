import logging
import logging.config
import logging.handlers
import os
from logging import CRITICAL, DEBUG, ERROR, INFO, WARNING, Logger

import colorlog

from ..base.exceptions import DuplicateError
from ..base.typing import Literal, Optional


class NullLogger(Logger):
    """获得一个空日志器，支持所有日志操作， 但是丢弃所有日志"""

    def __init__(self, name: str) -> None:
        super().__init__(name, CRITICAL)
        self.addHandler(logging.NullHandler())


class BotLogger(Logger):
    """日志器类"""

    LOGGERS: dict[str, "BotLogger"] = {}

    LOG_COLORS = {
        "DEBUG": "cyan,bold",
        "INFO": "green,bold",
        "WARNING": "yellow,bold",
        "ERROR": "red,bold",
        "CRITIAL": "red,bold,bg_white",
    }

    SECOND_LOG_COLORS = {
        "message": {
            "DEBUG": "cyan",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITIAL": "red,bg_white",
        }
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
        fmt_arr = [
            "%(asctime)s.%(msecs)03d",
            "%(log_color)s%(levelname)-8s%(reset)s",
            "%(module)-10s : %(blue)s%(lineno)-4d%(reset)s",
            "%(message_log_color)s%(message)s%(reset)s",
        ]
        if not no_tag:
            fmt_arr.insert(0, f"%(purple)s{name}%(reset)s")
        fmt_s = f" {' │ '.join(fmt_arr)}"
        fmt = colorlog.ColoredFormatter(
            fmt_s,
            datefmt="%Y-%m-%d %H:%M:%S",
            log_colors=BotLogger.LOG_COLORS,
            secondary_log_colors=BotLogger.SECOND_LOG_COLORS,
            reset=True,
        )
        fmt.default_msec_format = "%s.%03d"
        return fmt

    @staticmethod
    def _console_handler(fmt: logging.Formatter) -> logging.Handler:
        handler = logging.StreamHandler()
        handler.setFormatter(fmt)
        return handler

    @staticmethod
    def _file_fmt(name: str, no_tag: bool = False) -> logging.Formatter:
        fmt_arr = [
            "%(asctime)s.%(msecs)03d",
            "%(levelname)-8s",
            "%(module)-12s %(lineno)-4d %(funcName)-20s",
            "%(message)s",
        ]
        if not no_tag:
            fmt_arr.insert(0, name)
        fmt_s = " │ ".join(fmt_arr)
        fmt = logging.Formatter(
            fmt=fmt_s,
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        fmt.default_msec_format = "%s.%03d"
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
        """初始化一个日志器实例

        :param name: 日志器的名称（唯一）
        :param level: 日志等级
        :param to_console: 是否输出到 console
        :param to_dir: 保存日志文件的目录，为空则不保存文件
        :param no_tag: 记录日志时是否不标识日志器名称
        """

        if name in BotLogger.LOGGERS.keys():
            raise DuplicateError(f"名为 {name} 的日志器已存在，请修改 name")
        super().__init__(name, BotLogger.LEVEL_MAP[level])
        BotLogger.LOGGERS[name] = self
        self._con_handler: Optional[logging.Handler] = None
        self._handler_arr: list[logging.Handler] = []
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
            self._handler_arr.append(self._con_handler)

    def _add_file_handler(self, log_dir: str) -> None:
        handler = self._file_handler(
            self._file_fmt(self.name, self._no_tag), log_dir, self.name
        )
        self.addHandler(handler)
        self._handler_arr.append(handler)

    def setLevel(self, level: Literal["DEBUG", "ERROR", "INFO", "WARNING", "CRITICAL"]) -> None:  # type: ignore
        """设置日志等级

        日志等级自动应用于包含的所有 handler

        :param level: 日志等级字面量
        """
        super().setLevel(level)
        for handler in self._handler_arr:
            handler.setLevel(level)
