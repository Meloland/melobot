import traceback

from ..base.exceptions import ArgFormatInitError, ArgLackError, ArgVerifyFailed
from ..base.typing import (
    Any,
    Callable,
    Coroutine,
    ModuleType,
    Optional,
    ParseArgs,
    Void,
    VoidType,
)
from ..context.action import send


class FormatInfo:
    """命令参数格式化信息对象

    用于在命令参数格式化异常时传递信息。

    .. admonition:: 提示
       :class: tip

       一般无需手动实例化该类，多数情况会直接使用本类对象，或将本类用作类型注解。
    """

    def __init__(
        self,
        src: str | VoidType,
        src_desc: Optional[str],
        src_expect: Optional[str],
        idx: int,
        exc_type: Exception,
        exc_tb: ModuleType,
        cmd_name: str,
    ) -> None:
        #: 命令参数格式化前的原值
        self.src = src
        #: 命令参数值的功能描述
        self.src_desc = src_desc
        #: 命令参数值的值期待描述
        self.src_expect = src_expect
        #: 命令参数值的顺序（从 0 开始索引）
        self.idx = idx
        #: 命令参数格式化异常时的异常对象
        self.exc_type = exc_type
        #: 命令参数格式化异常时的调用栈信息
        self.exc_tb = exc_tb
        #: 命令参数所属命令的命令名
        self.cmd_name = cmd_name


class ArgFormatter:
    """命令参数格式化器

    用于格式化命令解析器解析出的命令参数。
    """

    def __init__(
        self,
        convert: Optional[Callable[[str], Any]] = None,
        verify: Optional[Callable[[Any], bool]] = None,
        src_desc: Optional[str] = None,
        src_expect: Optional[str] = None,
        default: Any = Void,
        default_replace_flag: Optional[str] = None,
        convert_fail: Optional[
            Callable[[FormatInfo], Coroutine[Any, Any, None]]
        ] = None,
        verify_fail: Optional[Callable[[FormatInfo], Coroutine[Any, Any, None]]] = None,
        arg_lack: Optional[Callable[[FormatInfo], Coroutine[Any, Any, None]]] = None,
    ) -> None:
        """初始化一个命令参数格式化器

        :param convert: 类型转换方法，为空则不进行类型转换
        :param verify: 值验证方法，为空则不对值进行验证
        :param src_desc: 命令参数值的功能描述
        :param src_expect: 命令参数值的值期待描述
        :param default: 命令参数值的默认值（默认值 :class:`.Void` 表示无值，而不是 :obj:`None` 表达的空值）
        :param default_replace_flag: 命令参数使用默认值的标志
        :param convert_fail: 类型转换失败的回调，为空则使用默认回调
        :param verify_fail: 值验证失败的回调，为空则使用默认回调
        :param arg_lack: 参数缺失的回调，为空则使用默认回调
        """
        self.convert = convert
        self.verify = verify
        self.src_desc = src_desc
        self.src_expect = src_expect
        self.default = default
        self.default_replace_flag = default_replace_flag
        if self.default is Void and self.default_replace_flag is not None:
            raise ArgFormatInitError(
                "初始化参数格式化器时，使用“默认值替换标记”必须同时设置默认值"
            )

        self.convert_fail = convert_fail
        self.verify_fail = verify_fail
        self.arg_lack = arg_lack

    def _get_val(self, args: ParseArgs, idx: int) -> Any:
        if self.default is Void:
            if args.vals is None or len(args.vals) < idx + 1:
                raise ArgLackError
            else:
                return args.vals[idx]
        if args.vals is None:
            args.vals = [self.default]
        elif len(args.vals) < idx + 1:
            args.vals.append(self.default)
        return args.vals[idx]

    async def format(
        self,
        cmd_name: str,
        args: ParseArgs,
        idx: int,
    ) -> bool:
        # 格式化参数为对应类型的变量
        try:
            src = self._get_val(args, idx)
            if (
                self.default_replace_flag is not None
                and src == self.default_replace_flag
            ):
                src = self.default
            res = self.convert(src) if self.convert is not None else src

            if self.verify is None:
                pass
            elif self.verify(res):
                pass
            else:
                raise ArgVerifyFailed
            args.vals[idx] = res  # type: ignore
            return True
        except ArgVerifyFailed as e:
            info = FormatInfo(
                src, self.src_desc, self.src_expect, idx, e, traceback, cmd_name
            )
            if self.verify_fail:
                await self.verify_fail(info)
            else:
                await self._verify_fail_default(info)
            return False
        except ArgLackError as e:
            info = FormatInfo(
                Void, self.src_desc, self.src_expect, idx, e, traceback, cmd_name
            )
            if self.arg_lack:
                await self.arg_lack(info)
            else:
                await self._arglack_default(info)
            return False
        except Exception as e:
            info = FormatInfo(
                src, self.src_desc, self.src_expect, idx, e, traceback, cmd_name
            )
            if self.convert_fail:
                await self.convert_fail(info)
            else:
                await self._convert_fail_default(info)
            return False

    async def _convert_fail_default(self, info: FormatInfo) -> None:
        e_class = info.exc_type.__class__.__name__
        src = info.src.__repr__() if isinstance(info.src, str) else info.src
        tip = f"第 {info.idx+1} 个参数"
        tip += (
            f"（{info.src_desc}）无法处理，给定的值为：{src}。"
            if info.src_desc
            else f"给定的值 {src} 无法处理。"
        )
        tip += f"参数要求：{info.src_expect}。" if info.src_expect else ""
        tip += f"\n详细错误描述：[{e_class}] {info.exc_type}"
        tip = f"命令 {info.cmd_name} 参数格式化失败：\n" + tip
        await send(tip)

    async def _verify_fail_default(self, info: FormatInfo) -> None:
        src = info.src.__repr__() if isinstance(info.src, str) else info.src
        tip = f"第 {info.idx+1} 个参数"
        tip += (
            f"（{info.src_desc}）不符合要求，给定的值为：{src}。"
            if info.src_desc
            else f"给定的值 {src} 不符合要求。"
        )
        tip += f"参数要求：{info.src_expect}。" if info.src_expect else ""
        tip = f"命令 {info.cmd_name} 参数格式化失败：\n" + tip
        await send(tip)

    async def _arglack_default(self, info: FormatInfo) -> None:
        tip = f"第 {info.idx+1} 个参数"
        tip += f"（{info.src_desc}）缺失。" if info.src_desc else "缺失。"
        tip += f"参数要求：{info.src_expect}。" if info.src_expect else ""
        tip = f"命令 {info.cmd_name} 参数格式化失败：\n" + tip
        await send(tip)
