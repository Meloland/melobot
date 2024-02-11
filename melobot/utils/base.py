import sys
import pathlib
import re


def this_dir(*path_str: str) -> str:
    """
    用于包内相对引用资源文件，解决包内相对路径不匹配的问题
    """
    fr = sys._getframe(1)
    call_file = fr.f_locals['__file__']
    return str(pathlib.Path(call_file).parent.joinpath(*path_str).resolve(strict=True))


def clear_cq(s: str) -> str:
    """
    去除文本中的所有 CQ 字符串
    """
    regex = re.compile(r'\[CQ:.*?\]')
    return regex.sub('', s)
