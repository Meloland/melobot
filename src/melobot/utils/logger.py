import io
import logging
import logging.config
import logging.handlers
import os
import sys
import types
from logging import CRITICAL

import colorlog
import rich.console
import rich.pretty
from better_exceptions import ExceptionFormatter

from ..base.abc import BaseLogger
from ..base.exceptions import BotValueError
from ..base.typing import Any, Callable, Literal, Optional


class NullLogger(BaseLogger):
    """获得一个空日志器，支持所有日志操作， 但是丢弃所有日志"""

    def __init__(self, name: str) -> None:
        super().__init__(name, CRITICAL)
        self.addHandler(logging.NullHandler())


class BotLogger(BaseLogger):
    """melobot 内置日志器类"""

    LOGGERS: dict[str, "BotLogger"] = {}

    LOG_COLORS = {
        "DEBUG": "cyan,bold",
        "INFO": "bold",
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

    @staticmethod
    def _console_fmt(name: str, no_tag: bool = False) -> logging.Formatter:
        fmt_arr = [
            "%(green)s%(asctime)s.%(msecs)03d%(reset)s",
            "%(log_color)s%(levelname)-8s%(reset)s",
            "%(blue)s%(module)-10s%(reset)s : %(green)s%(lineno)-4d%(reset)s -> %(blue)s%(funcName)-12s%(reset)s",
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
            "%(module)-10s : %(lineno)-4d -> %(funcName)-12s",
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
        level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO",
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
            raise BotValueError(f"名为 {name} 的日志器已存在，请修改 name")
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

    def setLevel(
        self, level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]  # type: ignore[override]
    ) -> None:
        """设置日志等级

        日志等级自动应用于包含的所有 handler

        :param level: 日志等级字面量
        """
        super().setLevel(level)
        for handler in self._handler_arr:
            handler.setLevel(level)
        self.__LOG_LEVEL_FLAG__ = BotLogger.LEVEL_MAP[level]


_EXC_FORMATTER = ExceptionFormatter(colored=False)


def get_exc_stack(e: Exception) -> str:
    """返回生成更好的异常字符串"""
    return "".join(
        _EXC_FORMATTER.format_exception(e.__class__, e, sys.exc_info()[2])
    ).strip()


_CONSOLE_IO = io.StringIO()
_CONSOLE = rich.console.Console(file=_CONSOLE_IO)


def get_rich_str(obj: object, max_string: Optional[int] = 1000) -> str:
    """返回使用 rich 格式化的 object"""
    _CONSOLE.print(
        rich.pretty.Pretty(
            obj,
            indent_guides=True,
            max_string=max_string,
            overflow="ignore",
        ),
        crop=False,
    )
    string = _CONSOLE_IO.getvalue().strip("\n")
    _CONSOLE_IO.seek(0)
    _CONSOLE_IO.truncate(0)
    return string


def log_exc(
    logger: BaseLogger,
    locals: dict[str, Any],
    e: Exception,
) -> None:
    logger.error(f"异常回溯栈：\n{get_exc_stack(e)}")
    logger.error(f"异常抛出点局部变量：\n{get_rich_str(locals)}")


def log_obj(log_method: Callable[..., None], obj: Any, prefix: str) -> None:
    obj_str = f"{prefix}：\n{get_rich_str(obj)}"
    log_method(obj_str)


def logger_patch(
    logger: Any,
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO",
) -> None:
    """修复任何非 :class:`.BotLogger` 类型的日志器，使其可以被用于 bot 实例初始化

    .. admonition:: 注意
       :class: caution

       非 :class:`.BotLogger` 类型的日志器，不使用该方法打补丁，无法被用于 bot 实例。但如果不用于 bot 实例，可以不打补丁。

    如果日志器的日志等级是可变的，请在更新后再次使用该方法修补

    :param logger: 任意日志器对象（支持 debug, info, warning, error, critical 方法即可）
    :param log_level: 日志器此时可以输出的最小日志等级（"DEBUG" 一端为小，"CRITICAL" 一端为大）
    """
    setattr(logger, BaseLogger.LEVEL_FLAG_NAME, BaseLogger.LEVEL_MAP[log_level])
    setattr(
        logger,
        BaseLogger.LEVEL_CHECK_METH_NAME,
        types.MethodType(BaseLogger.check_level_flag, logger),
    )
