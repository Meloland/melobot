from __future__ import annotations

from enum import Enum
from logging import CRITICAL, DEBUG, ERROR, INFO, WARNING

from typing_extensions import Any, Callable, Literal, TypeAlias, assert_never, cast, overload


class ExitCode(Enum):
    NORMAL = 0
    ERROR = 1
    RESTART = 2


# TODO: 考虑在最低支持 3.11 后，使用 logging.getLevelNamesMapping 兼容部分场景
class LogLevel(int, Enum):
    """日志等级枚举"""

    CRITICAL = CRITICAL
    ERROR = ERROR
    WARNING = WARNING
    INFO = INFO
    DEBUG = DEBUG


class LogicMode(Enum):
    """逻辑模式枚举类型"""

    AND = "and"
    OR = "or"
    NOT = "not"
    XOR = "xor"

    def get_operator(self) -> Callable[[Any, Any], bool]:
        match self:
            case LogicMode.AND:
                return lambda x, y: x and y
            case LogicMode.OR:
                return lambda x, y: x or y
            case LogicMode.NOT:
                return lambda x, _: not x
            case LogicMode.XOR:
                return lambda x, y: x ^ y
            case _:
                assert_never(f"不正确的逻辑类型 {self}")


CommonColorType: TypeAlias = Literal[
    # 标准色 (Standard, 0-7)
    "black",
    "red",
    "green",
    "yellow",
    "blue",
    "magenta",
    "cyan",
    "white",
    # 以此类推的高亮色 (Bright/High Intensity, 8-15)
    "bright_black",
    "bright_red",
    "bright_green",
    "bright_yellow",
    "bright_blue",
    "bright_magenta",
    "bright_cyan",
    "bright_white",
    # 复位
    "reset",
]

CommonColors = (
    "black",
    "red",
    "green",
    "yellow",
    "blue",
    "magenta",
    "cyan",
    "white",
    "bright_black",
    "bright_red",
    "bright_green",
    "bright_yellow",
    "bright_blue",
    "bright_magenta",
    "bright_cyan",
    "bright_white",
    "reset",
)


class Color:
    """颜色表示类"""

    @overload
    def __init__(self, arg1: CommonColorType | str) -> None: ...
    @overload
    def __init__(self, arg1: int, arg2: int, arg3: int) -> None: ...

    def __init__(
        self, arg1: CommonColorType | str | int, arg2: int | None = None, arg3: int | None = None
    ) -> None:
        if isinstance(arg1, str):
            if arg1 in CommonColors:
                self.is_common = True
                return
            else:
                if not arg1.startswith("#"):
                    raise ValueError("十六进制颜色值必须以'#'开头")
                hex_s = arg1.lstrip("#")
                if not (0 <= int(hex_s, 16) <= 0xFFFFFF):
                    raise ValueError("十六进制颜色值必须在 #000000 到 #FFFFFF 之间")
                self.rgb = cast(
                    tuple[int, int, int], tuple(int(hex_s[i : i + 2], 16) for i in (0, 2, 4))
                )
                self.is_common = False
        else:
            r, g, b = arg1, cast(int, arg2), cast(int, arg3)
            if not all(0 <= x <= 255 for x in (r, g, b)):
                raise ValueError(f"RGB 值必须都在 [0, 255] 之间，但是提供了 {arg1}, {arg2}, {arg3}")
            self.rgb = (r, g, b)
            self.is_common = False

    @property
    def hex(self) -> str:
        if self.is_common:
            raise AttributeError("常用颜色没有十六进制表示")
        return f"#{self.rgb[0]:02x}{self.rgb[1]:02x}{self.rgb[2]:02x}"

    @property
    def hsl(self) -> tuple[float, float, float]:
        if self.is_common:
            raise AttributeError("常用颜色没有 HSL 表示")

        r, g, b = self.rgb[0] / 255.0, self.rgb[1] / 255.0, self.rgb[2] / 255.0
        c_max = max(r, g, b)
        c_min = min(r, g, b)
        delta = c_max - c_min
        li = (c_max + c_min) / 2
        if delta == 0:
            h, s = 0.0, 0.0
        else:
            s = delta / (1 - abs(2 * li - 1))
            if c_max == r:
                h = ((g - b) / delta) % 6
            elif c_max == g:
                h = (b - r) / delta + 2
            else:  # c_max == b
                h = (r - g) / delta + 4
            h *= 60
        return (h, s * 100, li * 100)

    def __getattribute__(self, name: str) -> Any:
        if name in CommonColors:
            raise AttributeError("不能在实例上获取常用颜色枚举，请使用类对象")
        return super().__getattribute__(name)

    black: Color
    red: Color
    green: Color
    yellow: Color
    blue: Color
    magenta: Color
    cyan: Color
    white: Color
    bright_black: Color
    bright_red: Color
    bright_green: Color
    bright_yellow: Color
    bright_blue: Color
    bright_magenta: Color
    bright_cyan: Color
    bright_white: Color
    reset: Color


setattr(Color, "black", Color("black"))
setattr(Color, "red", Color("red"))
setattr(Color, "green", Color("green"))
setattr(Color, "yellow", Color("yellow"))
setattr(Color, "blue", Color("blue"))
setattr(Color, "magenta", Color("magenta"))
setattr(Color, "cyan", Color("cyan"))
setattr(Color, "white", Color("white"))
setattr(Color, "bright_black", Color("bright_black"))
setattr(Color, "bright_red", Color("bright_red"))
setattr(Color, "bright_green", Color("bright_green"))
setattr(Color, "bright_yellow", Color("bright_yellow"))
setattr(Color, "bright_blue", Color("bright_blue"))
setattr(Color, "bright_magenta", Color("bright_magenta"))
setattr(Color, "bright_cyan", Color("bright_cyan"))
setattr(Color, "bright_white", Color("bright_white"))
setattr(Color, "reset", Color("reset"))
