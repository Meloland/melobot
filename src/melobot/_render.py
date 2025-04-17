from __future__ import annotations

import collections
import io
import os
import sys
from functools import lru_cache
from pathlib import Path
from types import FrameType, TracebackType

from typing_extensions import (
    TYPE_CHECKING,
    Any,
    Generator,
    Iterable,
    Iterator,
    Literal,
    Mapping,
    TypeAlias,
    cast,
    overload,
)

# 使用绝对导入保证子进程导入正确
from melobot._lazy import singleton

if TYPE_CHECKING:
    import rich.console
    import rich.highlighter
    from better_exceptions import ExceptionFormatter
    from rich.style import Style

_ORIGINAL_EXC_HOOK = sys.excepthook

# 使用 singleton 做 lazyload 优化


@singleton
def _get_tmp_console() -> "rich.console.Console":
    import rich.console

    return rich.console.Console(file=_TMP_CONSOLE_IO, record=True, color_system="256")


@singleton
def _get_exc_console() -> "rich.console.Console":
    import rich.console

    return rich.console.Console(file=sys.stderr, color_system="256")


@singleton
def _get_repr_highlighter() -> "rich.highlighter.Highlighter":
    import rich.highlighter

    return rich.highlighter.ReprHighlighter()


@singleton
def _get_style_highlighter_type() -> Any:
    from rich.highlighter import Highlighter

    if TYPE_CHECKING:
        from rich.text import Text

    class _StyleHighlighter(Highlighter):
        def __init__(self, style: "Style" | None) -> None:
            super().__init__()
            self.style = style

        def highlight(self, text: "Text") -> None:
            if self.style:
                text.stylize(self.style)

    return _StyleHighlighter


@singleton
def _get_exc_fmtter() -> "ExceptionFormatter":
    import better_exceptions
    from better_exceptions.formatter import ExceptionFormatter

    better_exceptions.SUPPORTS_COLOR = True
    better_exceptions.color.SUPPORTS_COLOR = True
    better_exceptions.formatter.SUPPORTS_COLOR = True
    # 修复在 windows powershell 显示错误的 bug
    better_exceptions.encoding.ENCODING = sys.stdout.encoding
    better_exceptions.formatter.ENCODING = sys.stdout.encoding

    class ExcFmtter(ExceptionFormatter):
        # 以下代码，由 better-exceptions 模块源代码修改而来
        # 原始版权 © 2016 Josh Junon
        # 原始许可：https://github.com/Qix-/better-exceptions/blob/master/LICENSE.txt
        def __init__(self) -> None:
            super().__init__()
            self._pipe_char = "\x00bold bright_black\x01│\x00/\x01"
            self._cap_char = "\x00bold bright_black\x01└\x00/\x01"
            self._hide_internal = False if EXC_SHOW_INTERNAL in os.environ else True
            self._flip = True if EXC_FLIP in os.environ else False
            self._colored = False

        def set_style(self, hide_internal: bool = True, flip: bool = False) -> None:
            self._hide_internal = hide_internal
            self._flip = flip

        def to_unicode(self, val: bytes | str) -> str:
            if isinstance(val, bytes):
                try:
                    return val.decode()
                except UnicodeDecodeError:
                    return val.decode("unicode-escape")
            return val

        def format_traceback_frame(
            self, tb: TracebackType
        ) -> tuple[tuple[str, int, str, str], str]:
            filename, lineno, function, _, color_source, relevant_values = (
                self.get_traceback_information(tb)
            )

            need_style = False
            if len(color_source.strip()):
                need_style = True
            else:
                color_source = ""
            lines = [color_source]

            for i in reversed(range(len(relevant_values))):
                _, col, val = relevant_values[i]
                pipe_cols = [pcol for _, pcol, _ in relevant_values[:i]]
                line = ""
                index = 0
                for pc in pipe_cols:
                    line += (" " * (pc - index)) + self._pipe_char
                    index = pc + 1

                line += "{}{} {}".format((" " * (col - index)), self._cap_char, val)
                lines.append(self._theme["inspect"](line) if self._colored else line)

            if need_style:
                lines[0] = f"\x00bold white\x01{lines[0]}\x00/\x01"
            formatted = "\n    ".join([self.to_unicode(x) for x in lines])
            return (filename, lineno, function, formatted), color_source

        def format_traceback(self, tb: TracebackType | None = None) -> tuple[str, str]:
            omit_last = False
            if not tb:
                try:
                    raise Exception
                except Exception:
                    omit_last = True
                    _, _, tb = sys.exc_info()
                    if tb is None:
                        raise ValueError("异常的回溯栈信息为空，无法格式化")

            frames = []
            final_source = ""
            while tb:
                if omit_last and not tb.tb_next:
                    break
                formatted, colored = self.format_traceback_frame(tb)
                collectable = True

                if self._flip:
                    formatted = (*formatted[:-1], "")
                    colored = ""

                try:
                    path = Path(formatted[0]).resolve(strict=True)
                    path_str = path.as_posix()
                except Exception:
                    pass
                else:
                    if self._hide_internal and _MAIN_PKG_PATH in path.parents:
                        collectable = False
                    else:
                        formatted = (path_str, *formatted[1:])

                if collectable:
                    final_source = colored
                    frames.append(formatted)
                tb = tb.tb_next

            lines = StackSummary.from_list(frames).format()
            return "".join(lines), final_source

        @lru_cache(maxsize=3)
        def format_exception(self, _: Any, exc: BaseException, tb: TracebackType | None) -> str:
            output = "".join(line for line in self._format_exception(exc, tb)).lstrip("\n").rstrip()
            if self._flip:
                output = output.replace("\n\n", "\n")
            return output

        def _format_exception(
            self, value: BaseException, tb: TracebackType | None, seen: set[int] | None = None
        ) -> Generator[str, None, None]:
            exc_type, exc_value, exc_traceback = type(value), value, tb
            if seen is None:
                seen = set()
            seen.add(id(exc_value))

            if exc_value:
                if exc_value.__cause__ is not None and id(exc_value.__cause__) not in seen:
                    for text in self._format_exception(
                        exc_value.__cause__, exc_value.__cause__.__traceback__, seen=seen
                    ):
                        yield text
                    yield "\nThe above exception was the direct cause of the following exception:\n\n"
                elif (
                    exc_value.__context__ is not None
                    and id(exc_value.__context__) not in seen
                    and not exc_value.__suppress_context__
                ):
                    for text in self._format_exception(
                        exc_value.__context__, exc_value.__context__.__traceback__, seen=seen
                    ):
                        yield text
                    yield "\nDuring handling of the above exception, another exception occurred:\n\n"

            if exc_traceback is not None:
                yield "Traceback (most recent call last):\n\n"

            formatted, colored_source = self.format_traceback(exc_traceback)
            formatted = formatted.replace("[", r"\[").replace("\x00", "[").replace("\x01", "]")
            yield formatted
            if not str(value) and exc_type is AssertionError:
                value.args = (colored_source,)

            te = TracebackException(type(value), value, None, compact=True)
            title_str = "".join(te.format_exception_only()).lstrip("\n").rstrip() + "\n"
            title_str = title_str.replace("[", r"\[").replace("\x00", "[").replace("\x01", "]")
            yield title_str

    return ExcFmtter()


_TMP_CONSOLE_IO = io.StringIO()
_HIGH_LIGHTWORDS = ["GET", "POST", "HEAD", "PUT", "DELETE", "OPTIONS", "TRACE", "PATCH"]
_MAIN_PKG_PATH = Path(cast(str, sys.modules["melobot"].__file__)).parent.resolve()


def get_rich_object(
    obj: object,
    max_len: int | None = 2000,
    style: "Style" | None = None,
    no_color: bool = False,
) -> tuple[str, str]:
    import rich.pretty

    if no_color:
        hl = _get_style_highlighter_type()(style=None)
    elif style:
        hl = _get_style_highlighter_type()(style)
    else:
        hl = None

    _get_tmp_console().print(
        rich.pretty.Pretty(
            obj,
            highlighter=hl,
            indent_guides=True,
            max_string=max_len,
            overflow="ignore",
            expand_all=True,
        ),
        crop=False,
    )
    colored_str = _TMP_CONSOLE_IO.getvalue().rstrip("\n")
    _TMP_CONSOLE_IO.seek(0)
    _TMP_CONSOLE_IO.truncate(0)
    return colored_str, _get_tmp_console().export_text().rstrip("\n")


def get_rich_repr(s: str, style: "Style" | None = None, no_color: bool = False) -> tuple[str, str]:
    from rich.text import Text

    if no_color:
        msg = Text(s)
    elif style:
        msg = Text(s, style=style)
    else:
        msg = _get_repr_highlighter()(Text(s))
        msg.highlight_words(_HIGH_LIGHTWORDS, "logging.keyword")

    _get_tmp_console().print(msg)
    colored_str = _TMP_CONSOLE_IO.getvalue()[:-1]
    _TMP_CONSOLE_IO.seek(0)
    _TMP_CONSOLE_IO.truncate(0)
    return colored_str, _get_tmp_console().export_text()[:-1]


def get_rich_str(s: str, markup: bool = True, emoji: bool = False) -> tuple[str, str]:
    _get_tmp_console().print(s, markup=markup, emoji=emoji, crop=False)
    colored_str = _TMP_CONSOLE_IO.getvalue()[:-1]
    _TMP_CONSOLE_IO.seek(0)
    _TMP_CONSOLE_IO.truncate(0)
    return colored_str, _get_tmp_console().export_text()[:-1]


# 从 3.13 开始，traceback 的格式化发生改变，导致 better-exceptions 无法使用
# 因此以下代码，用于在任意版本中兼容同一套 trackback 格式化
# TODO: 在升级最低版本到 3.11 后，考虑对 ExceptionGroup, add_note 的支持
# TODO: 在升级最低版本到 3.11 后，考虑使用 traceback.StackSummary.format_frame_summary 来过滤回溯栈帧，并更新 FrameInfo 和 Traceback

EXC_SHOW_INTERNAL = "MELOBOT_EXC_SHOW_INTERNAL"
EXC_FLIP = "MELOBOT_EXC_FLIP"


"""
以下代码，由 Python 3.10 的 traceback 模块源代码修改而来
原始版权 © 2001-2024 Python 软件基金会
原始许可：https://github.com/python/cpython/blob/main/LICENSE
"""
_RECURSIVE_CUTOFF = 3

_FrameSummaryTuple: TypeAlias = tuple[str, int, str, str | None]


class FrameSummary:
    __slots__ = ("filename", "lineno", "name", "_line", "locals")

    def __init__(
        self,
        filename: str,
        lineno: int | None,
        name: str,
        *,
        lookup_line: bool = True,
        locals: Mapping[str, str] | None = None,
        line: str | None = None,
    ) -> None:

        self.filename = filename
        self.lineno = lineno
        self.name = name
        self._line = line
        if lookup_line:
            self.line
        self.locals = {k: repr(v) for k, v in locals.items()} if locals else None

    def __eq__(self, other: object | tuple) -> bool:
        if isinstance(other, FrameSummary):
            return (
                self.filename == other.filename
                and self.lineno == other.lineno
                and self.name == other.name
                and self.locals == other.locals
            )
        if isinstance(other, tuple):
            return (self.filename, self.lineno, self.name, self.line) == other
        return NotImplemented

    @overload
    def __getitem__(self, pos: Literal[0]) -> str: ...
    @overload
    def __getitem__(self, pos: Literal[1]) -> int: ...
    @overload
    def __getitem__(self, pos: Literal[2]) -> str: ...
    @overload
    def __getitem__(self, pos: Literal[3]) -> str | None: ...
    @overload
    def __getitem__(self, pos: int) -> Any: ...
    @overload
    def __getitem__(self, pos: slice) -> tuple[Any, ...]: ...

    def __getitem__(self, pos: Any) -> Any:
        return (self.filename, self.lineno, self.name, self.line)[pos]

    def __iter__(self) -> Iterator[Any]:
        return iter([self.filename, self.lineno, self.name, self.line])

    def __repr__(self) -> str:
        return "<FrameSummary file {filename}, line {lineno} in {name}>".format(
            filename=self.filename, lineno=self.lineno, name=self.name
        )

    def __len__(self) -> Literal[4]:
        return 4

    @property
    def line(self) -> str | None:
        import linecache

        if self._line is None:
            if self.lineno is None:
                return None
            self._line = linecache.getline(self.filename, self.lineno)
        return self._line.strip()


class StackSummary(list[FrameSummary]):
    @classmethod
    def extract(
        cls,
        frame_gen: Iterable[tuple[FrameType, int]],
        *,
        limit: int | None = None,
        lookup_lines: bool = True,
        capture_locals: bool = False,
    ) -> StackSummary:
        import itertools
        import linecache

        if limit is None:
            limit = getattr(sys, "tracebacklimit", None)
            if limit is not None and limit < 0:
                limit = 0
        if limit is not None:
            if limit >= 0:
                frame_gen = itertools.islice(frame_gen, limit)
            else:
                frame_gen = collections.deque(frame_gen, maxlen=-limit)

        result = cls()
        fnames = set()
        for f, lineno in frame_gen:
            co = f.f_code
            filename = co.co_filename
            name = co.co_name

            fnames.add(filename)
            linecache.lazycache(filename, f.f_globals)
            if capture_locals:
                f_locals = f.f_locals
            else:
                f_locals = None
            result.append(FrameSummary(filename, lineno, name, lookup_line=False, locals=f_locals))
        for filename in fnames:
            linecache.checkcache(filename)
        if lookup_lines:
            for fs in result:
                fs.line
        return result

    @classmethod
    def from_list(cls, a_list: Iterable[FrameSummary | _FrameSummaryTuple]) -> StackSummary:
        result = StackSummary()
        for frame in a_list:
            if isinstance(frame, FrameSummary):
                result.append(frame)
            else:
                filename, lineno, name, line = frame
                result.append(FrameSummary(filename, lineno, name, line=line))
        return result

    def format(self) -> list[str]:
        result = []
        last_file = None
        last_line = None
        last_name = None
        count = 0
        for frame in self:
            if (
                last_file is None
                or last_file != frame.filename
                or last_line is None
                or last_line != frame.lineno
                or last_name is None
                or last_name != frame.name
            ):
                if count > _RECURSIVE_CUTOFF:
                    count -= _RECURSIVE_CUTOFF
                    result.append(
                        f"  [Previous line repeated {count} more "
                        f'time{"s" if count > 1 else ""}]\n\n'
                    )
                last_file = frame.filename
                last_line = frame.lineno
                last_name = frame.name
                count = 0
            count += 1
            if count > _RECURSIVE_CUTOFF:
                continue
            row = []
            row.append(
                f"  \x00blue\x01{frame.filename}\x00/\x01"
                f":\x00cyan\x01{frame.lineno}\x00/\x01"
                f" -> \x00magenta\x01{frame.name}\x00/\x01\n"
            )
            if frame.line:
                row.append("    {}\n\n".format(frame.line.strip()))
            if frame.locals:
                for name, value in sorted(frame.locals.items()):
                    row.append("    {name} = {value}\n\n".format(name=name, value=value))
            result.append("".join(row))
        if count > _RECURSIVE_CUTOFF:
            count -= _RECURSIVE_CUTOFF
            result.append(
                f"  [Previous line repeated {count} more " f'time{"s" if count > 1 else ""}]\n\n'
            )
        return result


class TracebackException:
    def __init__(
        self,
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: TracebackType | None,
        *,
        limit: int | None = None,
        lookup_lines: bool = True,
        capture_locals: bool = False,
        compact: bool = False,
        _seen: set[int] | None = None,
    ) -> None:
        is_recursive_call = _seen is not None
        if _seen is None:
            _seen = set()
        _seen.add(id(exc_value))

        self.stack = StackSummary.extract(
            self.walk_tb(exc_traceback),
            limit=limit,
            lookup_lines=lookup_lines,
            capture_locals=capture_locals,
        )
        self.exc_type = exc_type

        self._str = self._some_str(exc_value)
        if exc_type and issubclass(exc_type, SyntaxError):
            exc_value = cast(SyntaxError, exc_value)
            self.filename = exc_value.filename
            lno = exc_value.lineno
            self.lineno = str(lno) if lno is not None else None
            end_lno = exc_value.end_lineno
            self.end_lineno = str(end_lno) if end_lno is not None else None
            self.text = exc_value.text
            self.offset = exc_value.offset
            self.end_offset = exc_value.end_offset
            self.msg = exc_value.msg
        if lookup_lines:
            self._load_lines()
        self.__suppress_context__ = (
            exc_value.__suppress_context__ if exc_value is not None else False
        )

        self.__cause__: TracebackException | None
        self.__context__: TracebackException | None

        if not is_recursive_call:
            queue: list[tuple[TracebackException | None, BaseException | None]] = [
                (self, exc_value)
            ]
            while queue:
                te, e = queue.pop()
                if e and e.__cause__ is not None and id(e.__cause__) not in _seen:
                    cause = TracebackException(
                        type(e.__cause__),
                        e.__cause__,
                        e.__cause__.__traceback__,
                        limit=limit,
                        lookup_lines=lookup_lines,
                        capture_locals=capture_locals,
                        _seen=_seen,
                    )
                else:
                    cause = None

                if compact:
                    need_context = cause is None and e is not None and not e.__suppress_context__
                else:
                    need_context = True
                if (
                    e
                    and e.__context__ is not None
                    and need_context
                    and id(e.__context__) not in _seen
                ):
                    context = TracebackException(
                        type(e.__context__),
                        e.__context__,
                        e.__context__.__traceback__,
                        limit=limit,
                        lookup_lines=lookup_lines,
                        capture_locals=capture_locals,
                        _seen=_seen,
                    )
                else:
                    context = None
                te = cast(TracebackException, te)
                e = cast(BaseException, e)
                te.__cause__ = cause
                te.__context__ = context
                if cause:
                    queue.append((te.__cause__, e.__cause__))
                if context:
                    queue.append((te.__context__, e.__context__))

    @staticmethod
    def walk_tb(tb: TracebackType | None) -> Generator[tuple[FrameType, int], None, None]:
        while tb is not None:
            yield tb.tb_frame, tb.tb_lineno
            tb = tb.tb_next

    @staticmethod
    def _some_str(value: Any) -> str:
        try:
            return str(value)
        except Exception:
            return "<unprintable %s object>" % type(value).__name__

    def _format_final_exc_line(self, etype: str | None, value: str) -> str:
        valuestr = self._some_str(value)
        if value is None or not valuestr:
            line = "%s\n\n" % etype
        else:
            line = "\x00bold red\x01%s\x00/\x01: %s\n\n" % (etype, valuestr)
        return line

    @classmethod
    def from_exception(
        cls,
        exc: BaseException,
        *,
        limit: int | None = None,
        lookup_lines: bool = True,
        capture_locals: bool = False,
        compact: bool = False,
    ) -> TracebackException:
        return cls(
            type(exc),
            exc,
            exc.__traceback__,
            limit=limit,
            lookup_lines=lookup_lines,
            capture_locals=capture_locals,
            compact=compact,
        )

    def _load_lines(self) -> None:
        for frame in self.stack:
            frame.line

    def __eq__(self, other: object) -> bool:
        if isinstance(other, TracebackException):
            return self.__dict__ == other.__dict__
        return NotImplemented

    def __str__(self) -> str:
        return self._str

    def format_exception_only(self) -> Generator[str, None, None]:
        if self.exc_type is None:
            yield self._format_final_exc_line(None, self._str)
            return

        stype = self.exc_type.__qualname__
        smod = self.exc_type.__module__
        if smod not in ("__main__", "builtins"):
            if not isinstance(smod, str):
                smod = "<unknown>"
            stype = smod + "." + stype

        if not issubclass(self.exc_type, SyntaxError):
            yield self._format_final_exc_line(stype, self._str)
        else:
            yield from self._format_syntax_error(stype)

    def _format_syntax_error(self, stype: str) -> Generator[str, None, None]:
        filename_suffix = ""
        need_newline = False
        if self.lineno is not None:
            yield f"  \x00blue\x01{self.filename or 'string'}\x00/\x01:\x00cyan\x01{self.lineno}\x00/\x01\n"
            need_newline = True
        elif self.filename is not None:
            filename_suffix = " (\x00blue\x01{}\x00/\x01)".format(self.filename)

        text = self.text
        if text is not None:
            rtext = text.rstrip("\n")
            ltext = rtext.lstrip(" \n\f")
            spaces = len(rtext) - len(ltext)
            yield "    \x00bold white\x01{}\x00/\x01\n".format(ltext)

            if self.offset is not None:
                offset = self.offset
                end_offset = self.end_offset if self.end_offset not in {None, 0} else offset
                end_offset = cast(int, end_offset)
                if offset == end_offset or end_offset == -1:
                    end_offset = offset + 1

                colno = offset - 1 - spaces
                end_colno = end_offset - 1 - spaces
                if colno >= 0:
                    caretspace = ((c if c.isspace() else " ") for c in ltext[:colno])
                    yield "    {}{}".format("".join(caretspace), ("^" * (end_colno - colno)))
        msg = self.msg or "<no detail available>"
        prefix = "\n\n" if need_newline else ""
        yield "{}\x00bold red\x01{}\x00/\x01: {}{}\n".format(prefix, stype, msg, filename_suffix)


# -----------------------------------------------------------------------------


@lru_cache(maxsize=3)
def get_rich_exception(
    exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None
) -> tuple[str, str]:
    lines = _get_exc_fmtter().format_exception(exc_type, exc, tb)  # type: ignore[arg-type]
    colored_str, plain_str = get_rich_str(lines)
    return colored_str, plain_str


def _excepthook(
    exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None
) -> None:
    lines = _get_exc_fmtter().format_exception(exc_type, exc, tb)  # type: ignore[arg-type]
    _get_exc_console().print(lines, markup=True, emoji=False, crop=False)


def install_exc_hook() -> None:

    def ipy_excepthook_closure(ip: Any) -> None:
        # 以下代码，由 rich 模块源代码修改而来
        # 原始版权 © 2020 Will McGugan
        # 原始许可：https://github.com/Textualize/rich/blob/master/LICENSE
        tb_data = {}
        default_showtraceback = ip.showtraceback

        def ipy_show_traceback(*args: Any, **kwargs: Any) -> None:
            nonlocal tb_data
            tb_data = kwargs
            default_showtraceback(*args, **kwargs)

        def ipy_display_traceback(*args: Any, is_syntax: bool = False, **kwargs: Any) -> None:
            nonlocal tb_data
            exc_tuple = ip._get_exc_info()
            tb: TracebackType | None = None if is_syntax else exc_tuple[2]

            compiled = tb_data.get("running_compiled_code", False)
            tb_offset = tb_data.get("tb_offset", 1 if compiled else 0)
            for _ in range(tb_offset):
                if tb is None:
                    break
                tb = tb.tb_next

            _excepthook(exc_tuple[0], exc_tuple[1], tb)
            tb_data = {}

        ip._showtraceback = ipy_display_traceback
        ip.showtraceback = ipy_show_traceback
        ip.showsyntaxerror = lambda *args, **kwargs: ipy_display_traceback(
            *args, is_syntax=True, **kwargs
        )

    try:
        ip = get_ipython()  # type: ignore[name-defined] # noqa: F821
        ipy_excepthook_closure(ip)
    except Exception:
        sys.excepthook = _excepthook


EXC_FMT_FALLBACK = "MELOBOT_EXC_FMT_FALLBACK"
if EXC_FMT_FALLBACK not in os.environ:
    sys.excepthook = _excepthook


def uninstall_exc_hook() -> None:
    sys.excepthook = _ORIGINAL_EXC_HOOK


def set_traceback_style(hide_internal: bool = True, flip: bool = False) -> None:
    _get_exc_fmtter().set_style(hide_internal, flip)
