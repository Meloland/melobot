from __future__ import annotations

import io
import logging
import logging.handlers
import os
import sys
import traceback
import types
from abc import abstractmethod
from contextlib import contextmanager
from enum import Enum
from inspect import currentframe
from logging import CRITICAL, DEBUG, ERROR, INFO, WARNING
from logging import Logger as _Logger
from logging import _srcfile as _LOGGING_SRC_FILE

import colorlog
from rich.style import Style
from typing_extensions import Any, Callable, Generator, Literal, cast

from .._render import get_rich_exception, get_rich_object, get_rich_repr
from ..typ._enum import VoidType
from ..typ.base import T
from ..typ.cls import BetterABC
from ..utils.common import singleton

# 取消 better-exceptions 的猴子补丁
logging._loggerClass = (  # type:ignore[attr-defined]
    logging.Logger
)


class LogLevel(int, Enum):
    """日志等级枚举"""

    CRITICAL = CRITICAL
    ERROR = ERROR
    WARNING = WARNING
    INFO = INFO
    DEBUG = DEBUG


class GenericLogger(BetterABC):
    """通用日志器抽象类

    任何日志器实现本类接口，或通过 :func:`.logger_patch` 修补后，
    即可兼容 melobot 内部所有日志操作（也就可以用于 bot 初始化 :meth:`.Bot.`）
    """

    @abstractmethod
    def debug(self, msg: object) -> None:
        """`debug` 级别日志"""
        raise NotImplementedError

    @abstractmethod
    def info(self, msg: object) -> None:
        """`info` 级别日志"""
        raise NotImplementedError

    @abstractmethod
    def warning(self, msg: object) -> None:
        """`warning` 级别日志"""
        raise NotImplementedError

    @abstractmethod
    def error(self, msg: object) -> None:
        """`error` 级别日志"""
        raise NotImplementedError

    @abstractmethod
    def critical(self, msg: object) -> None:
        """`critical` 级别日志"""
        raise NotImplementedError

    @abstractmethod
    def exception(self, msg: object) -> None:
        """记录异常信息的日志"""
        raise NotImplementedError

    @abstractmethod
    def generic_lazy(
        self,
        msg: str,
        *arg_getters: Callable[[], str],
        level: LogLevel,
        with_exc: bool = False,
    ) -> None:
        """通用懒惰日志方法

        :param msg: 日志消息，可使用 %s 指定稍后填充的参数
        :param arg_getters: 填充消息 %s 位置的填充函数
        :param level: 日志等级
        :param with_exc: 是否记录异常栈信息
        """
        raise NotImplementedError

    @abstractmethod
    def generic_obj(
        self,
        msg: str,
        obj: T,
        *arg_getters: Callable[[], str],
        level: LogLevel = LogLevel.INFO,
    ) -> None:
        """通用记录对象日志方法

        :param msg: 附加的日志消息，可使用 %s 指定稍后填充的参数
        :param obj: 需要被日志记录的对象
        :param arg_getters: 填充消息 %s 位置的填充函数
        :param level: 日志等级
        """
        raise NotImplementedError


@singleton
class NullLogger(_Logger, GenericLogger):
    def __init__(self) -> None:
        super().__init__("__MELO_EMPTYLOGGER__", CRITICAL)
        self.addHandler(logging.NullHandler())

    def generic_lazy(
        self,
        msg: str,
        *arg_getters: Callable[[], str],
        level: LogLevel,
        with_exc: bool = False,
    ) -> None:
        return

    def generic_obj(
        self,
        msg: str,
        obj: T,
        *arg_getters: Callable[[], str],
        level: LogLevel = LogLevel.INFO,
    ) -> None:
        return


class Logger(_Logger, GenericLogger):
    """melobot 内置日志器

    推荐使用的日志器。实现了 :class:`GenericLogger` 接口，因此可以用于 melobot 内部日志记录。

    `debug`, `info`, `warning`, `error`, `critical`, `exception`
    等接口与 :class:`logging.Logger` 用法完全一致
    """

    def findCaller(
        self, stack_info: bool = False, stacklevel: int = 1
    ) -> tuple[str, int, str, str | None]:
        *ret, sinfo = find_caller_stack(stack_info, stacklevel)
        sinfo = f"\u0000{ret[0]},{ret[2]}"
        return cast(tuple[str, int, str, str | None], (*(ret[1:]), sinfo))

    def makeRecord(self, *args: Any, **kwargs: Any) -> logging.LogRecord:
        record = super().makeRecord(*args, **kwargs)
        sinfo = record.stack_info

        *sinfo_strs, caller_info = cast(str, sinfo).split("\u0000")
        *mod_name_strs, func_lineno = caller_info.split(",")
        record.mod_name = "".join(mod_name_strs)
        record.func_lineno = int(func_lineno)

        sinfo = "".join(sinfo_strs)
        if sinfo == "":
            sinfo = None
        record.stack_info = sinfo
        return record

    def __init__(
        self,
        name: str = "[default]",
        level: LogLevel = LogLevel.INFO,
        file_level: LogLevel = LogLevel.DEBUG,
        to_console: bool = True,
        to_dir: str | None = None,
        add_tag: bool = True,
        legacy: bool = False,
        yellow_warn: bool = True,
        red_error: bool = True,
        two_stream: bool = False,
    ) -> None:
        """初始化日志器

        :param name: 日志器的名称（唯一）
        :param level: 日志等级
        :param file_level: 日志文件的日志等级
        :param to_console: 是否输出到控制台
        :param to_dir: 保存日志文件的目录，为空则不保存文件
        :param add_tag: 记录日志时是否标识日志器名称
        :param legacy: 记录日志时是否使用传统样式（不对日志内容进行自动高亮，而是使用日志等级的五色）
        :param yellow_warn:
            记录 `LogLevel.WARN` 级别时，是否将日志内容着色为黄色。
            `legacy` 选项为 `True` 时此参数无效

        :param red_error:
            记录 `LogLevel.ERROR` 及以上级别时，是否将日志内容着色为红色。
            `legacy` 选项为 `True` 时此参数无效

        :param two_stream: 当使用记录到文件功能时，是否分离“常规日志”和“问题日志”（warning, error, critical）到不同的文件
        """
        super().__init__(name, LogLevel.DEBUG)
        self._handler_arr: list[logging.Handler] = []
        self._no_tag = not add_tag
        self._filter = _MeloLogFilter(name, yellow_warn, red_error, legacy)

        if to_console:
            con_handler = self._add_console_handler()
            con_handler.setLevel(level)

        if to_dir is None:
            pass
        elif not two_stream:
            self._add_file_handler(to_dir, name, file_level)
        else:
            normal_handler = self._add_file_handler(to_dir, f"{name}.out", file_level)
            normal_handler.addFilter(_NormalLvlFilter(name))
            self._add_file_handler(to_dir, f"{name}.err", max(file_level, LogLevel.WARNING))

    def _add_console_handler(self) -> logging.Handler:
        fmt = self._console_fmt(self.name, self._no_tag)
        handler = self._console_handler(fmt)
        handler.addFilter(self._filter)

        self.addHandler(handler)
        self._handler_arr.append(handler)
        return handler

    def _add_file_handler(
        self, log_dir: str, name: str, level: LogLevel = LogLevel.DEBUG
    ) -> logging.Handler:
        fmt = self._file_fmt(self.name, self._no_tag)
        handler = self._file_handler(fmt, log_dir, name, level)
        handler.addFilter(self._filter)

        self.addHandler(handler)
        self._handler_arr.append(handler)
        return handler

    @staticmethod
    def _make_fmt_nocache(fmt: logging.Formatter) -> None:
        _original_format = fmt.format

        def nocache_format(record: logging.LogRecord) -> str:
            record.exc_text = None
            return _original_format(record)

        fmt.format = nocache_format  # type: ignore[method-assign]

    @staticmethod
    def _console_fmt(name: str, no_tag: bool = False) -> logging.Formatter:
        fmt_arr = [
            "%(cyan)s%(asctime)s.%(msecs)03d%(reset)s",
            "%(log_color)s%(levelname)-7s%(reset)s",
            "%(blue)s%(mod_name)s%(reset)s:%(cyan)s%(func_lineno)d%(reset)s",
        ]
        if not no_tag:
            fmt_arr.insert(1, f"%(purple)s{name}%(reset)s")
        fmt_s = " | ".join(fmt_arr)
        msg_str_f = "%(log_color)s%(legacy_msg_str)s%(reset)s%(colored_msg_str)s"
        obj_str_f = "%(log_color)s%(legacy_obj)s%(reset)s%(colored_obj)s"
        fmt_s += f" - {msg_str_f}{obj_str_f}"

        fmt = colorlog.ColoredFormatter(fmt_s, datefmt="%Y-%m-%d %H:%M:%S", reset=True)
        fmt.default_msec_format = "%s.%03d"
        fmt.formatException = lambda exc_info: get_rich_exception(*exc_info)[0]  # type: ignore
        Logger._make_fmt_nocache(fmt)

        # 未知的 mypy bug 推断 fmt 为 Any 类型...
        return fmt  # type: ignore[no-any-return]

    @staticmethod
    def _console_handler(fmt: logging.Formatter) -> logging.Handler:
        handler = logging.StreamHandler()
        handler.setFormatter(fmt)
        return handler

    @staticmethod
    def _file_fmt(name: str, no_tag: bool = False) -> logging.Formatter:
        fmt_arr = [
            "%(asctime)s.%(msecs)03d",
            "%(levelname)-7s",
            "%(mod_name)s:%(func_lineno)d",
        ]
        if not no_tag:
            fmt_arr.insert(1, name)
        fmt_s = " | ".join(fmt_arr)
        fmt_s += " - %(msg_str)s%(obj)s"

        fmt = logging.Formatter(
            fmt=fmt_s,
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        fmt.default_msec_format = "%s.%03d"
        fmt.formatException = lambda exc_info: get_rich_exception(*exc_info)[1]  # type: ignore
        Logger._make_fmt_nocache(fmt)

        return fmt

    @staticmethod
    def _file_handler(
        fmt: logging.Formatter, log_dir: str, name: str, level: LogLevel
    ) -> logging.Handler:
        if not os.path.exists(log_dir):
            os.mkdir(log_dir)

        handler = logging.handlers.RotatingFileHandler(
            filename=os.path.join(log_dir, f"{name}.log"),
            maxBytes=1024 * 1024,
            backupCount=10,
            encoding="UTF-8",
        )
        handler.setLevel(level)
        handler.setFormatter(fmt)
        return handler

    def set_level(self, level: LogLevel) -> None:  # type: ignore[override]
        """设置日志等级

        日志等级自动应用于包含的所有 handler（但输出日志到文件的 handler 除外）

        :param level: 日志等级
        """
        super().setLevel(level)
        for handler in self._handler_arr:
            if not isinstance(handler, logging.handlers.RotatingFileHandler):
                handler.setLevel(level)

    def generic_lazy(
        self,
        msg: str,
        *arg_getters: Callable[[], str],
        level: LogLevel,
        with_exc: bool = False,
        stacklevel: int = 1,
    ) -> None:
        """懒惰日志方法

        :param msg: 日志消息，可使用 %s 指定稍后填充的参数
        :param arg_getters: 填充消息 %s 位置的填充函数
        :param level: 日志等级
        :param with_exc: 是否记录异常栈信息
        :param stacklevel: 打印日志时尝试解析的调用栈层级
        """
        if not self.isEnabledFor(level):
            return
        exc = sys.exc_info() if with_exc else None
        self._log(level, msg, tuple(g() for g in arg_getters), exc_info=exc, stacklevel=stacklevel)

    def generic_obj(
        self,
        msg: str,
        obj: T,
        *arg_getters: Callable[[], str],
        level: LogLevel = LogLevel.INFO,
        stacklevel: int = 1,
    ) -> None:
        """记录对象的日志方法

        :param msg: 附加的日志消息，可使用 %s 指定稍后填充的参数
        :param obj: 需要被日志记录的对象
        :param arg_getters: 填充消息 %s 位置的填充函数
        :param level: 日志等级
        :param stacklevel: 打印日志时尝试解析的调用栈层级
        """
        with self._filter.on_obj(obj):
            self.generic_lazy(msg + "\n", *arg_getters, level=level, stacklevel=stacklevel)


class _NormalLvlFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return logging.DEBUG <= record.levelno < logging.WARNING


class _MeloLogFilter(logging.Filter):
    def __init__(
        self,
        name: str = "",
        yellow_warn: bool = True,
        red_error: bool = True,
        legacy: bool = False,
    ) -> None:
        super().__init__(name)
        self._obj: Any = VoidType.VOID
        self._yellow_style = Style(color="yellow")
        self._red_style = Style(color="red")
        self._enable_yellow_warn = yellow_warn
        self._enable_red_error = red_error
        self._legacy = legacy

    def set_obj(self, obj: Any) -> None:
        self._obj = obj

    def clear_obj(self) -> None:
        self._obj = VoidType.VOID

    @contextmanager
    def on_obj(self, obj: Any) -> Generator[None, None, None]:
        try:
            self.set_obj(obj)
            yield
        finally:
            self.clear_obj()

    def filter(self, record: logging.LogRecord) -> Literal[True]:
        msg = str(record.msg)
        if record.args:
            msg = msg % record.args
        record.msg_str = msg
        self._fill_msg_and_obj(msg, record)
        return True

    def _fill_msg_and_obj(self, msg: str, record: logging.LogRecord) -> None:
        yellow_style = self._yellow_style
        red_style = self._red_style
        yellow_warn = self._enable_yellow_warn
        red_error = self._enable_red_error

        if self._legacy:
            record.legacy_msg_str, record.colored_msg_str, record.msg_str = msg, "", msg

            if self._obj is VoidType.VOID:
                record.legacy_obj, record.obj = "", ""
            else:
                record.legacy_obj = record.obj = get_rich_object(self._obj, no_color=True)[1]
            record.colored_obj = ""
            return

        record.legacy_msg_str = ""
        record.legacy_obj = ""

        if red_error and record.levelno >= ERROR:
            record.colored_msg_str, record.msg_str = get_rich_repr(msg, red_style)
        elif yellow_warn and ERROR > record.levelno >= WARNING:
            record.colored_msg_str, record.msg_str = get_rich_repr(msg, yellow_style)
        else:
            record.colored_msg_str, record.msg_str = get_rich_repr(msg)

        if self._obj is VoidType.VOID:
            record.colored_obj, record.obj = "", ""
        elif red_error and record.levelno >= ERROR:
            record.legacy_obj = record.obj = get_rich_object(self._obj, no_color=True)[1]
            record.colored_obj = ""
        elif yellow_warn and ERROR > record.levelno >= WARNING:
            record.legacy_obj = record.obj = get_rich_object(self._obj, no_color=True)[1]
            record.colored_obj = ""
        else:
            record.colored_obj, record.obj = get_rich_object(self._obj)


def _is_internal_frame(frame: types.FrameType) -> bool:
    filename = os.path.normcase(frame.f_code.co_filename)
    return filename in (_FILE, _LOGGING_SRC_FILE) or (
        "importlib" in filename and "_bootstrap" in filename
    )


def find_caller_stack(
    stack_info: bool = False, stacklevel: int = 1
) -> tuple[str, str, int, str, str | None]:
    f = currentframe()
    if f is None:
        return "<unknown module>", "<unknown file>", 0, "<unknown function>", "<unknown stackinfo>"

    while stacklevel > 0:
        next_f = f.f_back
        if next_f is None:
            break
        f = next_f
        if not _is_internal_frame(f):
            stacklevel -= 1
    co = f.f_code
    sinfo = None

    if stack_info:
        with io.StringIO() as sio:
            sio.write("Stack (most recent call last):\n")
            traceback.print_stack(f, file=sio)
            sinfo = sio.getvalue()
            if sinfo[-1] == "\n":
                sinfo = sinfo[:-1]

    assert isinstance(f.f_lineno, int)
    return f.f_globals["__name__"], co.co_filename, f.f_lineno, co.co_name, sinfo


def generic_obj_meth(
    logger: GenericLogger,
    msg: str,
    obj: T,
    *arg_getters: Callable[[], str],
    level: LogLevel = LogLevel.INFO,
) -> None:
    _getters = arg_getters + (lambda: get_rich_object(obj)[1],)
    logger.generic_lazy(msg + "\n%s", *_getters, level=level)


_FILE = os.path.normcase(generic_obj_meth.__code__.co_filename)
