import traceback
from abc import abstractmethod

from melobot.types.typing import Union

from ..types.exceptions import *
from ..types.typing import *


class TipGenerator:
    """
    提示信息生成器
    """
    @abstractmethod
    def gen(self, src: str, src_desc: Union[str, None], src_expect: Union[str, None], idx: int, 
            exc_type: Exception, exc_tb: traceback) -> str:
        pass


class StrFormatter:
    """
    字符串格式化器。将字符串格式化为对应类型的对象。
    格式化后可添加校验，也可自定义失败提示信息
    """
    def __init__(self, convert: Callable[[str], Any], verify: Callable[[Any], bool]=None, 
                 src_desc: str=None, src_expect: str=None, convert_tip_gen: TipGenerator=None, 
                 verify_tip_gen: TipGenerator=None, arglack_tip_gen: TipGenerator=None) -> None:
        self.convert = convert
        self.verify = verify
        self.src_desc = src_desc
        self.src_expect = src_expect
        self.out_convert_tip_gen = convert_tip_gen
        self.out_verify_tip_gen = verify_tip_gen
        self.out_arglack_tip_gen = arglack_tip_gen
    
    def format(self, args: ParseArgs, idx: int) -> None:
        """
        格式化字符串为对应类型的变量
        """
        try:
            if args.vals is None or len(args.vals) < idx+1:
                raise BotArgLackError
            src = args.vals[idx]
            res = self.convert(src)
            if self.verify is None:
                pass
            elif self.verify(res):
                pass
            else:
                raise BotArgCheckFailed
            args.vals[idx] = res
        except BotArgCheckFailed as e:
            if self.out_verify_tip_gen:
                tip = self.out_verify_tip_gen.gen(src, self.src_desc, self.src_expect, idx, e, traceback)
            else:
                tip = self._verify_tip_gen(src, idx)
            raise BotFormatFailed(tip)
        except BotArgLackError as e:
            if self.out_arglack_tip_gen:
                tip = self.out_arglack_tip_gen.gen(None, self.src_desc, self.src_expect, idx, e, traceback)
            else:
                tip = self._arglack_tip_gen(idx)
            raise BotFormatFailed(tip)
        except Exception as e:
            if self.out_convert_tip_gen:
                tip = self.out_convert_tip_gen.gen(src, self.src_desc, self.src_expect, idx, e, traceback)
            else:
                tip = self._convert_tip_gen(src, idx, e)
            raise BotFormatFailed(tip)
    
    def _convert_tip_gen(self, src: str, idx: int, exc_type: Exception) -> str:
        e_class = exc_type.__class__.__name__
        src = f'"{src}"' if isinstance(src, str) else src
        tip = f"第 {idx+1} 个参数"
        tip += f"（{self.src_desc}）无法处理，给定的值为：{src}。" if self.src_desc else f"给定的值 {src} 无法处理。"
        tip += f"参数要求：{self.src_expect}。" if self.src_expect else ''
        tip += f"\n详细错误描述：[{e_class}] {exc_type}"
        return tip
    
    def _verify_tip_gen(self, src: str, idx: int) -> str:
        src = f'"{src}"' if isinstance(src, str) else src
        tip = f"第 {idx+1} 个参数"
        tip += f"（{self.src_desc}）不符合要求，给定的值为：{src}。" if self.src_desc else f"给定的值 {src} 不符合要求。"
        tip += f"参数要求：{self.src_expect}。" if self.src_expect else ''
        return tip
    
    def _arglack_tip_gen(self, idx: int) -> str:
        tip = f"第 {idx+1} 个参数"
        tip += f"（{self.src_desc}）缺失。" if self.src_desc else f"缺失。"
        tip += f"参数要求：{self.src_expect}。" if self.src_expect else ''
        return tip

