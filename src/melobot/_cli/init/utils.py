import keyword
import re
from pathlib import Path
from types import ModuleType


def get_module_filename(mod: ModuleType) -> str:
    if mod.__file__ is None:
        raise ValueError(f"模块 {mod.__name__} 无法获取文件名")
    return Path(mod.__file__).parts[-1]


IDENTFIER_REGEX = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def is_valid_identifier(name: str) -> bool:
    if not IDENTFIER_REGEX.match(name):
        return False
    if keyword.iskeyword(name):
        return False
    return True


def get_name_parts(name: str) -> tuple[str, ...]:
    if name == "":
        return ("",)

    # 规则 1：在“多个连续大写字母”与“大写+小写字母”之间插入下划线
    # 这一步处理类似 HTtp 的情况 -> H_Ttp
    s1 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)

    # 规则 2：在“小写字母或数字”与“大写字母”之间插入下划线
    # 这一步处理类似 hTtp -> h_Ttp 以及 HtTp -> Ht_Tp 的情况
    s2 = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s1)

    # 最终将所有字符转换为小写
    return tuple(s2.lower().split("_"))
