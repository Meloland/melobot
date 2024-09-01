from __future__ import annotations

import io
import logging
import logging.config
import logging.handlers
import os
import sys
import traceback
import types
from contextlib import contextmanager
from enum import Enum
from inspect import currentframe
from logging import CRITICAL, DEBUG, ERROR, INFO, WARNING
from logging import Logger as _Logger
from logging import _srcfile as _LOGGING_SRC_FILE
from typing import Any, Callable, Generator, Literal, Optional

import colorlog
import rich.console
import rich.pretty
from better_exceptions import ExceptionFormatter
from rich.highlighter import ReprHighlighter
from rich.text import Text

from ..typ import BetterABC, T, abstractmethod
from ..utils import singleton

_CONSOLE_IO = io.StringIO()
_CONSOLE = rich.console.Console(file=_CONSOLE_IO, record=True, color_system="256")
_REPR_HIGHLIGHTER = ReprHighlighter()
_HIGH_LIGHTWORDS = [
    "GET",
    "POST",
    "HEAD",
    "PUT",
    "DELETE",
    "OPTIONS",
    "TRACE",
    "PATCH",
    "MELOBOT",
    "melobot",
]


def _get_rich_object(obj: object, max_len: Optional[int] = 2000) -> tuple[str, str]:
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
    colored_str = _CONSOLE_IO.getvalue().rstrip("\n")
    _CONSOLE_IO.seek(0)
    _CONSOLE_IO.truncate(0)
    return colored_str, _CONSOLE.export_text().rstrip("\n")


def _get_rich_repr(s: str) -> tuple[str, str]:
    msg = _REPR_HIGHLIGHTER(Text(s))
    msg.highlight_words(_HIGH_LIGHTWORDS, "logging.keyword")
    _CONSOLE.print(msg)
    colored_str = _CONSOLE_IO.getvalue()[:-1]
    _CONSOLE_IO.seek(0)
    _CONSOLE_IO.truncate(0)
    return colored_str, _CONSOLE.export_text()[:-1]


_EXC_FORMATTER = ExceptionFormatter(colored=True)
_NO_COLOR_EXC_FORMATTER = ExceptionFormatter(colored=False)


class MeloFilter(logging.Filter):
    def __init__(self, name: str = "") -> None:
        super().__init__(name)
        self.obj = ""
        self.colored_obj = ""

    def set_obj(self, obj: Any) -> None:
        self.colored_obj, self.obj = _get_rich_object(obj)

    def clear_obj(self) -> None:
        self.colored_obj, self.obj = "", ""

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
        record.colored_msg_str, record.msg_str = _get_rich_repr(msg)
        record.mod_name, record.func_name, record.func_lineno = _current_finfo()
        record.colored_obj, record.obj = self.colored_obj, self.obj
        return True


class LogLevel(int, Enum):
    CRITICAL = CRITICAL
    DEBUG = DEBUG
    ERROR = ERROR
    INFO = INFO
    WARNING = WARNING


_FILE = os.path.normcase(_get_rich_object.__code__.co_filename)


def _is_internal_frame(frame: types.FrameType) -> bool:
    filename = os.path.normcase(frame.f_code.co_filename)
    return filename in (_FILE, _LOGGING_SRC_FILE) or (
        "importlib" in filename and "_bootstrap" in filename
    )


def _current_finfo() -> tuple[str, str, int]:
    frame = currentframe()
    while frame:
        if not _is_internal_frame(frame):
            return (
                frame.f_globals["__name__"],
                frame.f_code.co_name,
                frame.f_lineno,
            )
        frame = frame.f_back
    return "<unknown module>", "<unknown file>", -1


class GenericLogger(BetterABC):
    # pylint: disable=duplicate-code

    @abstractmethod
    def debug(self, msg: object) -> None:
        raise NotImplementedError

    @abstractmethod
    def info(self, msg: object) -> None:
        raise NotImplementedError

    @abstractmethod
    def warning(self, msg: object) -> None:
        raise NotImplementedError

    @abstractmethod
    def error(self, msg: object) -> None:
        raise NotImplementedError

    @abstractmethod
    def critical(self, msg: object) -> None:
        raise NotImplementedError

    @abstractmethod
    def exception(self, msg: object) -> None:
        raise NotImplementedError

    @abstractmethod
    def generic_lazy(
        self,
        msg: str,
        *arg_getters: Callable[[], str],
        level: LogLevel,
        with_exc: bool = False,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def generic_obj(
        self,
        msg: str,
        obj: T,
        *arg_getters: Callable[[], str],
        level: LogLevel = LogLevel.INFO,
    ) -> None:
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
    """melobot 内置日志器类"""

    __instances__: dict[str, "Logger"] = {}

    def __new__(cls, name: str = "melobot", /, *args: Any, **kwargs: Any) -> Logger:
        if name in Logger.__instances__:
            return Logger.__instances__[name]
        obj = super().__new__(cls)
        Logger.__instances__[name] = obj
        return obj

    def __init__(
        self,
        name: str = "melobot",
        /,
        level: LogLevel = LogLevel.INFO,
        to_console: bool = True,
        to_dir: Optional[str] = None,
        no_tag: bool = True,
    ) -> None:
        """初始化一个日志器实例

        :param name: 日志器的名称（唯一）
        :param level: 日志等级
        :param to_console: 是否输出到 console
        :param to_dir: 保存日志文件的目录，为空则不保存文件
        :param no_tag: 记录日志时是否不标识日志器名称
        """
        if (
            hasattr(self, "_built")
            and self._built  # pylint: disable=access-member-before-definition
        ):
            return

        super().__init__(name, level)
        self._con_handler: Optional[logging.Handler] = None
        self._handler_arr: list[logging.Handler] = []
        self._no_tag = no_tag
        self._filter = MeloFilter(name)

        if to_console:
            self._add_console_handler()
        if to_dir is not None:
            self._add_file_handler(to_dir)

        self._built: bool = True

    def _add_console_handler(self) -> None:
        if self._con_handler is None:
            fmt = self._console_fmt(self.name, self._no_tag)
            self._con_handler = self._console_handler(fmt)
            self._con_handler.addFilter(self._filter)

            self.addHandler(self._con_handler)
            self._handler_arr.append(self._con_handler)

    def _add_file_handler(self, log_dir: str) -> None:
        fmt = self._file_fmt(self.name, self._no_tag)
        handler = self._file_handler(fmt, log_dir, self.name)
        handler.addFilter(self._filter)

        self.addHandler(handler)
        self._handler_arr.append(handler)

    @staticmethod
    def _make_fmt_nocache(fmt: logging.Formatter) -> None:
        _origin_format = fmt.format

        def nocache_format(record: logging.LogRecord) -> str:
            record.exc_text = None
            return _origin_format(record)

        fmt.format = nocache_format  # type: ignore[method-assign]

    @staticmethod
    def _console_fmt(name: str, no_tag: bool = False) -> logging.Formatter:
        fmt_arr = [
            "%(green)s%(asctime)s.%(msecs)03d%(reset)s",
            "%(log_color)s%(levelname)-7s%(reset)s",
            "%(blue)s%(mod_name)s%(reset)s:%(blue)s%(func_name)s%(reset)s"
            + ":%(cyan)s%(func_lineno)d%(reset)s",
        ]
        if not no_tag:
            fmt_arr.insert(0, f"%(purple)s{name}%(reset)s")
        fmt_s = " | ".join(fmt_arr)
        fmt_s += " - %(colored_msg_str)s%(colored_obj)s"

        fmt = colorlog.ColoredFormatter(fmt_s, datefmt="%Y-%m-%d %H:%M:%S", reset=True)
        fmt.default_msec_format = "%s.%03d"
        fmt.formatException = lambda exc_info: "".join(  # type: ignore[assignment]
            _EXC_FORMATTER.format_exception(*exc_info)
        )
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
            "%(mod_name)s:%(func_name)s:%(func_lineno)d",
        ]
        if not no_tag:
            fmt_arr.insert(0, name)
        fmt_s = " | ".join(fmt_arr)
        fmt_s += " - %(msg_str)s%(obj)s"

        fmt = logging.Formatter(
            fmt=fmt_s,
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        fmt.default_msec_format = "%s.%03d"
        fmt.formatException = lambda exc_info: "".join(  # type: ignore
            _NO_COLOR_EXC_FORMATTER.format_exception(*exc_info)
        )
        Logger._make_fmt_nocache(fmt)

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

    def setLevel(self, level: LogLevel) -> None:  # type: ignore[override]
        """设置日志等级

        日志等级自动应用于包含的所有 handler

        :param level: 日志等级字面量
        """
        super().setLevel(level)
        for handler in self._handler_arr:
            handler.setLevel(level)

    def findCaller(
        self, stack_info: bool = False, stacklevel: int = 1
    ) -> tuple[str, int, str, str | None]:
        f = currentframe()
        if f is None:
            return "<unknown file>", 0, "<unknown function>", "<unknown stackinfo>"

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
        return co.co_filename, f.f_lineno, co.co_name, sinfo

    def generic_lazy(
        self,
        msg: str,
        *arg_getters: Callable[[], str],
        level: LogLevel,
        with_exc: bool = False,
    ) -> None:
        if not self.isEnabledFor(level):
            return
        exc = sys.exc_info() if with_exc else None
        self._log(level, msg, tuple(g() for g in arg_getters), exc_info=exc)

    def generic_obj(
        self,
        msg: str,
        obj: T,
        *arg_getters: Callable[[], str],
        level: LogLevel = LogLevel.INFO,
    ) -> None:
        if isinstance(self, Logger):
            with self._filter.on_obj(obj):
                self.generic_lazy(msg + "\n", *arg_getters, level=level)
        else:
            _getters = arg_getters + (lambda: _get_rich_object(obj)[1],)
            self.generic_lazy(msg + "\n%s", *_getters, level=level)
