import traceback

from ..context.action import send
from ..types.exceptions import *
from ..types.typing import *


class FormatInfo:
    """
    格式化信息对象
    """

    def __init__(
        self,
        src: str,
        src_desc: Optional[str],
        src_expect: Optional[str],
        idx: int,
        exc_type: Exception,
        exc_tb: ModuleType,
        cmd_name: str,
    ) -> None:
        self.src = src
        self.src_desc = src_desc
        self.src_expect = src_expect
        self.idx = idx
        self.exc_type = exc_type
        self.exc_tb = exc_tb
        self.cmd_name = cmd_name


class ArgFormatter:
    """
    参数格式化器。将参数格式化为对应类型的对象。格式化后可添加校验，也可自定义失败提示信息。
    还可设置默认值。不提供默认值参数时为 Void，代表不使用默认值
    """

    def __init__(
        self,
        convert: Callable[[str], Any] = None,
        verify: Callable[[Any], bool] = None,
        src_desc: str = None,
        src_expect: str = None,
        default: Any = Void,
        default_replace_flag: str = None,
        convert_fail: Callable[[FormatInfo], Coroutine[Any, Any, None]] = None,
        verify_fail: Callable[[FormatInfo], Coroutine[Any, Any, None]] = None,
        arglack: Callable[[FormatInfo], Coroutine[Any, Any, None]] = None,
    ) -> None:
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
        self.arg_lack = arglack

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
        """
        格式化参数为对应类型的变量
        """
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
            args.vals[idx] = res
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
                None, self.src_desc, self.src_expect, idx, e, traceback, cmd_name
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
        tip += f"（{info.src_desc}）缺失。" if info.src_desc else f"缺失。"
        tip += f"参数要求：{info.src_expect}。" if info.src_expect else ""
        tip = f"命令 {info.cmd_name} 参数格式化失败：\n" + tip
        await send(tip)
