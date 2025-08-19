import re
from dataclasses import dataclass
from functools import lru_cache
from types import TracebackType

from typing_extensions import Any, Callable, Iterable, Iterator, NamedTuple, Optional, Sequence

from ...exceptions import UtilError
from ...log.reflect import logger
from ...typ._enum import VoidType
from ...typ.base import SyncOrAsyncCallable
from ...utils.base import to_async
from .base import AbstractParseArgs, Parser


class CmdParseError(UtilError): ...


class FormatError(CmdParseError): ...


class ArgValidateFailed(FormatError): ...


class ArgLackError(FormatError): ...


@dataclass
class CmdArgs(AbstractParseArgs):
    """命令参数对象"""

    name: str
    tag: str | None
    vals: list[Any]

    def __len__(self) -> int:
        return len(self.vals)

    def __bool__(self) -> bool:
        return True


class CmdArgFormatInfo:
    """命令参数格式化信息对象

    用于在命令参数格式化异常时传递信息。
    """

    def __init__(
        self,
        src: str | VoidType,
        src_desc: Optional[str],
        src_expect: Optional[str],
        idx: int,
        exc: Exception,
        exc_tb: Optional[TracebackType],
        name: str,
    ) -> None:
        #: 命令参数所属命令的命令名
        self.name: str = name
        #: 命令参数格式化前的原值，参数缺失时是 VoidType.VOID
        self.src: str | VoidType = src
        #: 命令参数值的功能描述
        self.src_desc: str | None = src_desc
        #: 命令参数值的值期待描述
        self.src_expect: str | None = src_expect
        #: 命令参数值的顺序（从 0 开始索引）
        self.idx: int = idx
        #: 命令参数格式化异常时的异常对象
        self.exc: Exception = exc
        #: 命令参数格式化异常时的调用栈信息
        self.exc_tb: TracebackType | None = exc_tb


class CmdArgFormatter:
    """命令参数格式化器

    用于格式化命令解析器解析出的命令参数。搭配命令解析器 :class:`.CmdParser` 使用
    """

    def __init__(
        self,
        convert: Optional[Callable[[str], Any]] = None,
        validate: Optional[Callable[[Any], bool]] = None,
        src_desc: Optional[str] = None,
        src_expect: Optional[str] = None,
        default: Any = VoidType.VOID,
        default_replace_flag: Optional[str] = None,
        convert_fail: Optional[SyncOrAsyncCallable[[CmdArgFormatInfo], None]] = None,
        validate_fail: Optional[SyncOrAsyncCallable[[CmdArgFormatInfo], None]] = None,
        arg_lack: Optional[SyncOrAsyncCallable[[CmdArgFormatInfo], None]] = None,
    ) -> None:
        """初始化一个命令参数格式化器

        :param convert: 类型转换方法，为空则不进行类型转换
        :param validate: 值验证方法，为空则不对值进行验证
        :param src_desc: 命令参数值的功能描述
        :param src_expect: 命令参数值的值期待描述
        :param default: 命令参数值的默认值（默认值 :class:`.Void` 表示无值，而不是 :obj:`None` 表达的空值）
        :param default_replace_flag: 命令参数使用默认值的标志
        :param convert_fail: 类型转换失败的回调，为空则使用默认回调
        :param validate_fail: 值验证失败的回调，为空则使用默认回调
        :param arg_lack: 参数缺失的回调，为空则执行默认规则
        """
        self.convert = convert
        self.validate = validate
        self.src_desc = src_desc
        self.src_expect = src_expect

        self.default = default
        self.default_replace_flag = default_replace_flag
        if self.default is VoidType.VOID and self.default_replace_flag is not None:
            raise CmdParseError("初始化参数格式化器时，使用“默认值替换标记”必须同时设置默认值")

        self.convert_fail = to_async(convert_fail) if convert_fail is not None else None
        self.validate_fail = to_async(validate_fail) if validate_fail is not None else None
        self.arg_lack = to_async(arg_lack) if arg_lack is not None else None

    def _get_val(self, args: CmdArgs, idx: int) -> Any:
        if self.default is VoidType.VOID:
            if len(args.vals) < idx + 1:
                raise ArgLackError
            return args.vals[idx]

        if len(args.vals) < idx + 1:
            args.vals.append(self.default)

        return args.vals[idx]

    async def format(self, group_id: str, args: CmdArgs, idx: int) -> bool:
        # 格式化参数为对应类型的变量
        try:
            src = self._get_val(args, idx)
            if self.default_replace_flag is not None and src == self.default_replace_flag:
                src = self.default
            res = self.convert(src) if self.convert is not None else src

            if self.validate is None or self.validate(res):
                pass
            else:
                raise ArgValidateFailed
            args.vals[idx] = res
            return True

        except ArgValidateFailed as e:
            info = CmdArgFormatInfo(
                src, self.src_desc, self.src_expect, idx, e, e.__traceback__, group_id
            )
            if self.validate_fail:
                await self.validate_fail(info)
            else:
                await self._validate_fail_default(info)
            return False

        except ArgLackError as e:
            info = CmdArgFormatInfo(
                VoidType.VOID,
                self.src_desc,
                self.src_expect,
                idx,
                e,
                e.__traceback__,
                group_id,
            )
            if self.arg_lack:
                await self.arg_lack(info)
            else:
                await self._arglack_default(info)
            return False

        except Exception as e:
            info = CmdArgFormatInfo(
                src, self.src_desc, self.src_expect, idx, e, e.__traceback__, group_id
            )
            if self.convert_fail:
                await self.convert_fail(info)
            else:
                await self._convert_fail_default(info)
            return False

    async def _convert_fail_default(self, info: CmdArgFormatInfo) -> None:
        e_class = f"{info.exc.__class__.__module__}.{info.exc.__class__.__qualname__}"
        src = repr(info.src) if isinstance(info.src, str) else info.src

        tip = f"第 {info.idx + 1} 个参数"
        tip += (
            f"（{info.src_desc}）无法处理，给定的值为：{src}。"
            if info.src_desc
            else f"给定的值 {src} 无法处理。"
        )

        tip += f"参数要求：{info.src_expect}。" if info.src_expect else ""
        tip += f"\n详细错误描述：[{e_class}] {info.exc}"
        tip = f"命令 {info.name} 参数格式化失败：\n{tip}"
        logger.warning(tip)

    async def _validate_fail_default(self, info: CmdArgFormatInfo) -> None:
        src = repr(info.src) if isinstance(info.src, str) else info.src

        tip = f"第 {info.idx + 1} 个参数"
        tip += (
            f"（{info.src_desc}）不符合要求，给定的值为：{src}。"
            if info.src_desc
            else f"给定的值 {src} 不符合要求。"
        )

        tip += f"参数要求：{info.src_expect}。" if info.src_expect else ""
        tip = f"命令 {info.name} 参数格式化失败：\n{tip}"
        logger.warning(tip)

    async def _arglack_default(self, info: CmdArgFormatInfo) -> None:
        tip = f"第 {info.idx + 1} 个参数"
        tip += f"（{info.src_desc}）缺失。" if info.src_desc else "缺失。"
        tip += f"参数要求：{info.src_expect}。" if info.src_expect else ""
        tip = f"命令 {info.name} 参数格式化失败：\n{tip}"
        logger.warning(tip)


class CmdParseResult(NamedTuple):
    cmd_dict: dict[str, list[str]]
    pure_text: str


def _regex_split(string: str, regex: re.Pattern, pop_first: bool = True) -> Iterator[str]:
    temp_string = regex.sub("\u0000", string)
    temp_list = re.split("\u0000", temp_string)
    if pop_first:
        temp_list.pop(0)
    return filter(lambda x: x != "", temp_list)


@lru_cache(maxsize=128)
def _cmd_parse(
    text: str,
    start_regex: re.Pattern[str],
    sep_regex: re.Pattern[str],
    strip_blank: bool = True,
) -> CmdParseResult:
    pure_string = text.strip() if strip_blank else text
    cmd_seqs = (
        list(_regex_split(s, sep_regex, False)) for s in _regex_split(pure_string, start_regex)
    )
    seqs_filter = filter(lambda x: len(x) > 0, cmd_seqs)

    cmd_dict: dict[str, list[str]] = {}
    for seq in seqs_filter:
        if len(seq) == 0:
            continue
        if seq[0] in cmd_dict:
            continue
        cmd_dict[seq[0]] = seq[1:]

    return CmdParseResult(cmd_dict, pure_string)


class CmdParser(Parser):
    """命令解析器

    通过解析命令名和命令参数的形式，解析字符串。
    """

    def __init__(
        self,
        cmd_start: str | Iterable[str],
        cmd_sep: str | Iterable[str],
        targets: str | Sequence[str],
        fmtters: Optional[Sequence[Optional[CmdArgFormatter]]] = None,
        tag: str | None = None,
        strict: bool = False,
    ) -> None:
        """初始化一个命令解析器

        .. admonition:: 注意
           :class: caution

           - 命令起始符和命令间隔符不允许包含：引号，各种括号，反斜杠，数字，英文，控制字符及各类空白字符。
           - 命令起始符不能是命令间隔符的子序列，反之亦然。

        :param cmd_start: 命令起始符（可以是字符串或字符串列表）
        :param cmd_sep: 命令间隔符（可以是字符串或字符串列表）
        :param targets: 匹配的命令名
        :param formatters: 格式化器（可以包含空值，即此位置的参数无格式化）
        :param tag: 标签，此标签将被填充给本解析器产生的 :class:`.CmdArgs` 对象的 `tag` 属性
        :param strict: 是否启用严格模式（解析前不去除字符串两端的空白字符）
        """
        super().__init__()
        if isinstance(targets, str):
            self.targets = (targets,)
        else:
            self.targets = targets if isinstance(targets, tuple) else tuple(targets)
        if len(self.targets) < 1:
            raise CmdParseError("命令解析器至少需要一个目标命令名")

        if isinstance(cmd_start, str):
            start_tokens = {cmd_start}
        else:
            start_tokens = cmd_start if isinstance(cmd_start, set) else set(cmd_start)
        if isinstance(cmd_sep, str):
            sep_tokens = {cmd_sep}
        else:
            sep_tokens = cmd_sep if isinstance(cmd_sep, set) else set(cmd_sep)

        self.start_tokens = tuple(start_tokens)
        self.ban_regex = re.compile(r"[\'\"\\\(\)\[\]\{\}\r\n\ta-zA-Z0-9]")
        self.arg_tag = tag if tag is not None else self.targets[0]
        self.fmtters = fmtters
        self.need_strip = not strict

        if self.ban_regex.findall(f"{''.join(cmd_start)}{''.join(cmd_sep)}"):
            raise CmdParseError("存在命令解析器不支持的命令起始符，或命令间隔符")

        _regex = re.compile(r"([\`\-\=\~\!\@\#\$\%\^\&\*\(\)\_\+\[\]\{\}\|\:\,\.\/\<\>\?])")

        if len(sep_tokens & start_tokens):
            raise CmdParseError("命令解析器起始符不能和间隔符重合")
        cmd_seps = "|".join(_regex.sub(r"\\\1", token) for token in sep_tokens)
        cmd_starts = "|".join(_regex.sub(r"\\\1", token) for token in start_tokens)
        self.sep_regex = re.compile(cmd_seps)
        self.start_regex = re.compile(cmd_starts)

    async def parse(self, text: str) -> Optional[CmdArgs]:
        cmd_dict, pure_text = _cmd_parse(text, self.start_regex, self.sep_regex, self.need_strip)
        if not pure_text.startswith(self.start_tokens):
            return None

        args_dict = {
            cmd_name: CmdArgs(cmd_name, self.arg_tag, vals) for cmd_name, vals in cmd_dict.items()
        }

        for group_id in self.targets:
            args = args_dict.get(group_id)
            if args is not None:
                break
        else:
            return None

        if self.fmtters is None:
            return args

        for idx, fmt in enumerate(self.fmtters):
            if fmt is None:
                continue
            status = await fmt.format(group_id, args, idx)
            if not status:
                return None

        args.vals = args.vals[: len(self.fmtters)]
        return args


class CmdParserFactory:
    """命令解析器的工厂

    预先存储命令起始符和命令间隔符，指定匹配的命令名后返回一个命令解析器。
    """

    def __init__(self, cmd_start: str | Iterable[str], cmd_sep: str | Iterable[str]) -> None:
        """初始化一个命令解析器的工厂

        .. admonition:: 注意
           :class: caution

           - 命令起始符和命令间隔符不允许包含：引号，各种括号，反斜杠，数字，英文，控制字符及各类空白字符。
           - 命令起始符不能是命令间隔符的子序列，反之亦然。

        :param cmd_start: 命令起始符（可以是字符串或字符串列表）
        :param cmd_sep: 命令间隔符（可以是字符串或字符串列表）
        """
        self.cmd_start = cmd_start
        self.cmd_sep = cmd_sep

    def get(
        self,
        targets: str | Sequence[str],
        formatters: Optional[Sequence[Optional[CmdArgFormatter]]] = None,
        tag: str | None = None,
        strict: bool = False,
    ) -> CmdParser:
        """生成匹配指定命令名的命令解析器

        :param targets: 匹配的命令名
        :param formatters: 格式化器（列表可以包含空值，即此位置的参数无格式化选项）
        :param tag: 标签，此标签将被填充给解析器产生的 :class:`.CmdArgs` 对象的 `tag` 属性
        :param strict: 是否启用严格模式（解析前不去除字符串两端的空白字符）
        """
        return CmdParser(self.cmd_start, self.cmd_sep, targets, formatters, tag, strict)
