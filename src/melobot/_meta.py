from __future__ import annotations

from typing import Any, ClassVar, Generic, Literal, NamedTuple, NoReturn

from .typ import T

__version__ = "3.0.0rc13"


def _version_str_to_info(s: str) -> VersionInfo:
    parts = s.split(".")
    major = int(parts[0])
    minor = int(parts[1])

    remains = parts[2]
    flag: Literal["alpha", "beta", "pre-release", "final"]

    if "a" in remains:
        _parts = remains.split("a")
        flag = "alpha"
    elif "b" in remains:
        _parts = remains.split("b")
        flag = "beta"
    elif "rc" in remains:
        _parts = remains.split("rc")
        flag = "pre-release"
    else:
        _parts = [remains, remains]
        flag = "final"

    micro = int(_parts[0])
    serial = int(_parts[1])
    return VersionInfo(major, minor, micro, flag, serial)


class ReadOnlyAttr(Generic[T]):
    def __init__(self, val: T):
        self.val = val

    def __get__(self, obj: Any, klass: Any = None) -> T:
        return self.val

    def __set__(self, obj: Any, value: T) -> NoReturn:
        raise AttributeError("只读属性无法重新设定值")


class VersionInfo(NamedTuple):
    """版本信息元组"""

    major: int
    """主要版本号

    变更时伴随重大架构更新（下一代 melobot 才会更改）
    """

    minor: int
    """次要版本号

    变更时伴随重要的功能更新
    """

    micro: int
    """微版本号

    变更时伴随不重要的功能更新，或是漏洞/错误修复
    """

    releaselevel: Literal["alpha", "beta", "pre-release", "final"]
    """发行级别

    `micro` 更新，一般直接使用 `final` 发行级别

    `minor` 更新，可能历经：
        - `alpha` -> `beta` -> `pre-release` -> `final` （极少）
        - `pre-release` -> `final` （较多）
        - `final` （少）

    `major` 更新，一定历经：
        - `alpha` -> `beta` -> `pre-release` -> `final`
    """

    serial: int
    """发行序列号，若 `releaselevel` 为 "final"，则该值与 `micro` 相同

    否则可以视为具体 `releaselevel` 的子版本号，相当于 `nano` 级版本号
    """


class MetaInfoMeta(type):
    ver = ReadOnlyAttr[str](__version__)
    ver_info = ReadOnlyAttr[VersionInfo](_version_str_to_info(__version__))
    name = ReadOnlyAttr[str]("melobot")
    desc = ReadOnlyAttr[str]("A bot framework with much high level features.")
    src = ReadOnlyAttr[str]("https://github.com/Meloland/melobot")
    logo = ReadOnlyAttr[str](
        "\n".join(
            (
                r"                _       _           _   ",
                r" _ __ ___   ___| | ___ | |__   ___ | |_ ",
                r"| '_ ` _ \ / _ \ |/ _ \| '_ \ / _ \| __|",
                r"| | | | | |  __/ | (_) | |_) | (_) | |_ ",
                r"|_| |_| |_|\___|_|\___/|_.__/ \___/ \__|",
            )
        )
    )


class MetaInfo(metaclass=MetaInfoMeta):
    """melobot 项目只读元信息"""

    ver: ClassVar[str]
    """melobot 版本

       :meta hide-value:
    """

    ver_info: ClassVar[VersionInfo]
    """melobot 版本信息

       :meta hide-value:
    """

    name: ClassVar[str]
    """melobot 项目名称

       :meta hide-value:
    """

    desc: ClassVar[str]
    """melobot 项目描述

       :meta hide-value:
    """

    src: ClassVar[str]
    """melobot 项目地址

       :meta hide-value:
    """

    logo: ClassVar[str]
    """melobot ascii art 图标

       :meta hide-value:
    """
