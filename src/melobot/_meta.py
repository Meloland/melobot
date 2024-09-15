from typing import Any, Generic, NoReturn

from .typ import T

__version__ = "3.0.0rc5"


class ReadOnlyAttr(Generic[T]):
    def __init__(self, val: T):
        self.val = val

    def __get__(self, obj: Any, klass: Any = None) -> T:
        return self.val

    def __set__(self, obj: Any, value: T) -> NoReturn:
        raise AttributeError("只读属性无法重新设定值")


class MetaInfoMeta(type):
    ver = ReadOnlyAttr[str](__version__)
    name = ReadOnlyAttr[str]("melobot")
    desc = ReadOnlyAttr[str]("A bot framework with much high level features.")
    src = ReadOnlyAttr[str]("https://github.com/Meloland/melobot")
    logo = ReadOnlyAttr[str](
        "\n".join(
            (
                r" __  __      _       ____        _   ",
                r"|  \/  | ___| | ___ | __ )  ___ | |_ ",
                r"| |\/| |/ _ \ |/ _ \|  _ \ / _ \| __|",
                r"| |  | |  __/ | (_) | |_) | (_) | |_ ",
                r"|_|  |_|\___|_|\___/|____/ \___/ \__|",
            )
        )
    )


class MetaInfo(metaclass=MetaInfoMeta):
    """元信息类

    .. admonition:: 提示
       :class: tip

       一般无需手动实例化该类，多数情况会直接使用本类的属性，或将本类用作类型注解。
    """

    ver: str
    """melobot 版本

       :meta hide-value:
    """

    name: str
    """melobot 项目名称

       :meta hide-value:
    """

    desc: str
    """melobot 项目描述

       :meta hide-value:
    """

    src: str
    """melobot 项目地址

       :meta hide-value:
    """

    logo: str
    """melobot ascii art 图标

       :meta hide-value:
    """
