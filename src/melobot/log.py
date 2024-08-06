import io
import logging
import logging.config
import logging.handlers
import os
import sys
import types
from contextvars import ContextVar, Token
from enum import Enum
from logging import CRITICAL, DEBUG, ERROR, INFO, WARNING, Logger

import colorlog
import rich.console
import rich.pretty
from better_exceptions import ExceptionFormatter

from .exceptions import BotLoggerError
from .typing import Any, Optional, cast
from .utils import singleton

_CONSOLE_IO = io.StringIO()
_CONSOLE = rich.console.Console(file=_CONSOLE_IO, record=True, color_system="windows")


def get_rich_str(obj: object, max_len: Optional[int] = 1000) -> tuple[str, str]:
    """返回使用 rich 格式化的 object"""
    _CONSOLE.print(
        rich.pretty.Pretty(
            obj,
            indent_guides=True,
            max_string=max_len,
            overflow="ignore",
            expand_all=True,
        ),
        crop=False,
    )
    colored_str = _CONSOLE_IO.getvalue().strip("\n")
    _CONSOLE_IO.seek(0)
    _CONSOLE_IO.truncate(0)
    return colored_str, _CONSOLE.export_text()


_EXC_FORMATTER = ExceptionFormatter(colored=True)
_NO_COLOR_EXC_FORMATTER = ExceptionFormatter(colored=False)


def _get_fmtted_exc(e: BaseException) -> str:
    """返回生成更好的异常字符串"""
    return "".join(
        _NO_COLOR_EXC_FORMATTER.format_exception(e.__class__, e, e.__traceback__)
    )


class ObjectFilter(logging.Filter):
    def __init__(self, name: str = "") -> None:
        super().__init__(name)
        self.obj = ""
        self.colored_obj = ""

    def set(self, obj: Any) -> None:
        self.colored_obj, self.obj = get_rich_str(obj)
        self.colored_obj += "\n"
        self.obj += "\n"

    def clear(self) -> None:
        self.colored_obj, self.obj = "", ""

    def filter(self, record):
        record.colored_obj, record.obj = self.colored_obj, self.obj
        return True


class LogLevel(int, Enum):
    CRITICAL = CRITICAL
    DEBUG = DEBUG
    ERROR = ERROR
    INFO = INFO
    WARNING = WARNING


class NullLogger(Logger):
    def __init__(self, name: str) -> None:
        super().__init__(name, CRITICAL)
        self.addHandler(logging.NullHandler())
        logger_patch(self, LogLevel.CRITICAL)


class MeloLogger(Logger):
    """melobot 内置日志器类"""

    LOGGERS: dict[str, "MeloLogger"] = {}

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
    def make_fmt_nocache(fmt: logging.Formatter) -> None:
        _origin_format = fmt.format

        def nocache_format(record: logging.LogRecord) -> str:
            record.exc_text = None
            return _origin_format(record)

        fmt.format = nocache_format  # type: ignore[method-assign]

    @staticmethod
    def _console_fmt(name: str, no_tag: bool = False) -> logging.Formatter:
        fmt_arr = [
            "%(green)s%(asctime)s.%(msecs)03d%(reset)s",
            "%(log_color)s%(levelname)-8s%(reset)s",
            "%(blue)s%(module)-10s%(reset)s : %(green)s%(lineno)-4d%(reset)s -> %(blue)s%(funcName)-12s%(reset)s",
            "%(message_log_color)s%(message)s%(reset)s%(colored_obj)s",
        ]
        if not no_tag:
            fmt_arr.insert(0, f"%(purple)s{name}%(reset)s")
        fmt_s = f" {' │ '.join(fmt_arr)}"

        fmt = colorlog.ColoredFormatter(
            fmt_s,
            datefmt="%Y-%m-%d %H:%M:%S",
            log_colors=MeloLogger.LOG_COLORS,
            secondary_log_colors=MeloLogger.SECOND_LOG_COLORS,
            reset=True,
        )
        fmt.default_msec_format = "%s.%03d"
        fmt.formatException = lambda exc_info: "".join(
            _EXC_FORMATTER.format_exception(*exc_info)
        )
        MeloLogger.make_fmt_nocache(fmt)

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
            "%(message)s%(obj)s",
        ]
        if not no_tag:
            fmt_arr.insert(0, name)
        fmt_s = " │ ".join(fmt_arr)

        fmt = logging.Formatter(
            fmt=fmt_s,
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        fmt.default_msec_format = "%s.%03d"
        fmt.formatException = lambda exc_info: "".join(  # type: ignore
            _NO_COLOR_EXC_FORMATTER.format_exception(*exc_info)
        )
        MeloLogger.make_fmt_nocache(fmt)

        return fmt

    @staticmethod
    def _file_handler(fmt: logging.Formatter, log_dir: str, name: str) -> logging.Handler:
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
        level: LogLevel = LogLevel.INFO,
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

        if name in MeloLogger.LOGGERS.keys():
            raise BotLoggerError(f"名为 {name} 的日志器已存在，请修改 name")

        super().__init__(name, level)
        MeloLogger.LOGGERS[name] = self

        self._con_handler: Optional[logging.Handler] = None
        self._handler_arr: list[logging.Handler] = []
        self._no_tag = no_tag
        self._obj_filter = ObjectFilter(name)
        self.__LEVEL_FLAG__ = level

        if to_console:
            self._add_console_handler()
        if to_dir is not None:
            self._add_file_handler(to_dir)

    def _add_console_handler(self) -> None:
        if self._con_handler is None:
            fmt = self._console_fmt(self.name, self._no_tag)
            self._con_handler = self._console_handler(fmt)
            self._con_handler.addFilter(self._obj_filter)

            self.addHandler(self._con_handler)
            self._handler_arr.append(self._con_handler)

    def _add_file_handler(self, log_dir: str) -> None:
        fmt = self._file_fmt(self.name, self._no_tag)
        handler = self._file_handler(fmt, log_dir, self.name)
        handler.addFilter(self._obj_filter)

        self.addHandler(handler)
        self._handler_arr.append(handler)

    def setLevel(self, level: LogLevel) -> None:  # type: ignore[override]
        """设置日志等级

        日志等级自动应用于包含的所有 handler

        :param level: 日志等级字面量
        """
        super().setLevel(level)
        for handler in self._handler_arr:
            handler.setLevel(level)

        self.__LOG_LEVEL_FLAG__ = level

    def _check_level(self, level: LogLevel = LogLevel.INFO) -> bool:
        """检查日志器是否可以输出指定日志等级的日志"""
        return level >= self.__LEVEL_FLAG__

    def exc(
        self,
        prefix: str = "出现异常：",
        e: Optional[BaseException] = None,
        locals: Optional[dict[str, Any]] = None,
    ) -> None:
        """更好的用于记录异常的方法

        :param prefix: 记录时的前缀信息
        :param e: 异常对象
        :param locals: 需要记录的局部变量，为空则不记录
        """
        _exc = sys.exc_info()[1] if e is None else e
        exc_str = f"[{_exc.__class__.__qualname__}] {str(_exc)}"

        if hasattr(self, "exception"):
            self.exception(f"{prefix}{exc_str}")
        else:
            fmt_exc = _get_fmtted_exc(cast(BaseException, _exc))
            self.error(f"{prefix}{exc_str}\n{fmt_exc}")

        if locals is not None:
            self.obj(locals, "异常抛出点局部变量", level=LogLevel.ERROR)

    def obj(
        self,
        obj: Any,
        prefix: str,
        prefix_fmt: str = "%s：\n",
        level: LogLevel = LogLevel.DEBUG,
    ) -> None:
        """在日志时记录指定的对象

        :param obj: 对象
        :param prefix: 记录时的前缀信息
        :param prefix_fmt: 前缀信息的格式化字符串
        :param level: 记录的日志等级，默认为 DEBUG
        """
        log_meth = getattr(self, level._name_.lower())

        if isinstance(self, MeloLogger):
            self._obj_filter.set(obj)
            log_meth(prefix_fmt % prefix)
            self._obj_filter.clear()
        else:
            log_meth(f"{prefix_fmt % prefix}{get_rich_str(obj)[1]}")


def logger_patch(logger: Any, log_level: LogLevel = LogLevel.INFO) -> None:
    """修复任何非 :class:`.BotLogger` 类型的日志器，使其可以被用于 bot 实例初始化

    .. admonition:: 注意
       :class: caution

       非 :class:`.BotLogger` 类型的日志器，不使用该方法打补丁，无法被用于 bot 实例。但如果不用于 bot 实例，可以不打补丁。

    如果日志器的日志等级是可变的，请在更新后再次使用该方法修补

    :param logger: 任意日志器对象（支持 debug, info, warning, error, critical 方法即可）
    :param log_level: 日志器此时可以输出的最小日志等级（"DEBUG" 一端为小，"CRITICAL" 一端为大）
    """
    setattr(logger, "__LEVEL_FLAG__", log_level)
    setattr(
        logger,
        MeloLogger._check_level.__name__,
        types.MethodType(MeloLogger._check_level, logger),
    )
    setattr(logger, MeloLogger.exc.__name__, types.MethodType(MeloLogger.exc, logger))
    setattr(logger, MeloLogger.obj.__name__, types.MethodType(MeloLogger.obj, logger))


@singleton
class LoggerLocal:
    """Logger 实例自动上下文"""

    def __init__(self) -> None:
        object.__setattr__(self, "__storage__", ContextVar("logger_ctx"))
        self.__storage__: ContextVar[MeloLogger]

    def get(self) -> MeloLogger:
        try:
            return self.__storage__.get()
        except LookupError:
            raise BotLoggerError("当前上下文中不存在 logger 实例，无法获取")

    def add(self, ctx: MeloLogger) -> Token:
        return self.__storage__.set(ctx)

    def remove(self, token: Token) -> None:
        self.__storage__.reset(token)


def get_logger() -> MeloLogger:
    return LoggerLocal().get()
