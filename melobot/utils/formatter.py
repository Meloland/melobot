import traceback
from abc import abstractmethod

from ..types.exceptions import *
from ..types.typing import *


class TipGenerator:
    """
    提示信息生成器
    """

    @abstractmethod
    def gen(
        self,
        src: str,
        src_desc: Optional[str],
        src_expect: Optional[str],
        idx: int,
        exc_type: Exception,
        exc_tb: traceback,
    ) -> str:
        pass


class ArgFormatter:
    """
    参数格式化器。将参数格式化为对应类型的对象。格式化后可添加校验，也可自定义失败提示信息。
    还可设置默认值。不提供默认值参数时为 Null，代表不使用默认值
    """

    def __init__(
        self,
        convert: Callable[[str], Any] = None,
        verify: Callable[[Any], bool] = None,
        src_desc: str = None,
        src_expect: str = None,
        default: Any = Void,
        default_replace_flag: str = None,
        convert_tip_gen: TipGenerator = None,
        verify_tip_gen: TipGenerator = None,
        arglack_tip_gen: TipGenerator = None,
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

        self.out_convert_tip_gen = convert_tip_gen
        self.out_verify_tip_gen = verify_tip_gen
        self.out_arglack_tip_gen = arglack_tip_gen

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

    def format(self, args: ParseArgs, idx: int) -> None:
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
        except ArgVerifyFailed as e:
            if self.out_verify_tip_gen:
                tip = self.out_verify_tip_gen.gen(
                    src, self.src_desc, self.src_expect, idx, e, traceback
                )
            else:
                tip = self._verify_tip_gen(src, idx)
            raise ArgFormatFailed(tip)
        except ArgLackError as e:
            if self.out_arglack_tip_gen:
                tip = self.out_arglack_tip_gen.gen(
                    None, self.src_desc, self.src_expect, idx, e, traceback
                )
            else:
                tip = self._arglack_tip_gen(idx)
            raise ArgFormatFailed(tip)
        except Exception as e:
            if self.out_convert_tip_gen:
                tip = self.out_convert_tip_gen.gen(
                    src, self.src_desc, self.src_expect, idx, e, traceback
                )
            else:
                tip = self._convert_tip_gen(src, idx, e)
            raise ArgFormatFailed(tip)

    def _convert_tip_gen(self, src: str, idx: int, exc_type: Exception) -> str:
        e_class = exc_type.__class__.__name__
        src = src.__repr__() if isinstance(src, str) else src
        tip = f"第 {idx+1} 个参数"
        tip += (
            f"（{self.src_desc}）无法处理，给定的值为：{src}。"
            if self.src_desc
            else f"给定的值 {src} 无法处理。"
        )
        tip += f"参数要求：{self.src_expect}。" if self.src_expect else ""
        tip += f"\n详细错误描述：[{e_class}] {exc_type}"
        return tip

    def _verify_tip_gen(self, src: str, idx: int) -> str:
        src = src.__repr__() if isinstance(src, str) else src
        tip = f"第 {idx+1} 个参数"
        tip += (
            f"（{self.src_desc}）不符合要求，给定的值为：{src}。"
            if self.src_desc
            else f"给定的值 {src} 不符合要求。"
        )
        tip += f"参数要求：{self.src_expect}。" if self.src_expect else ""
        return tip

    def _arglack_tip_gen(self, idx: int) -> str:
        tip = f"第 {idx+1} 个参数"
        tip += f"（{self.src_desc}）缺失。" if self.src_desc else f"缺失。"
        tip += f"参数要求：{self.src_expect}。" if self.src_expect else ""
        return tip
