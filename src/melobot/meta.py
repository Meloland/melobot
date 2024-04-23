import os
import sys
from typing import Any


class ReadOnly(type):
    def __new__(cls, name, bases, dic):
        _class = super().__new__(cls, name, bases, dic)
        super().__setattr__(
            _class,
            "__cvars__",
            tuple(k for k in dic if not k.startswith("__")),
        )
        return _class

    def __setattr__(self, name: str, value: Any) -> None:
        if name in self.__cvars__:  # type: ignore[attr-defined]
            raise AttributeError(
                f"{self.__name__} 类的类属性 {name} 是只读的，无法修改"
            )
        return super().__setattr__(name, value)

    def __instance_setattr(self, name: str, value: Any) -> None:
        if hasattr(self, name):
            raise AttributeError(
                f"{self.__class__.__name__} 类的实例属性 {name} 是只读的，无法修改"
            )
        super(self.__class__, self).__setattr__(name, value)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.__setattr__ = ReadOnly.__instance_setattr  # type: ignore[assignment]
        return super().__call__(*args, **kwargs)


__version__ = "2.6.1"


class MetaInfo(metaclass=ReadOnly):
    """元信息类

    .. admonition:: 提示
       :class: tip

       一般无需手动实例化该类，多数情况会直接使用本类的属性，或将本类用作类型注解。
    """

    VER: str = __version__
    """melobot 版本

       :meta hide-value:
    """

    PROJ_NAME: str = "melobot"
    """melobot 项目名称

       :meta hide-value:
    """

    PROJ_DESC: str = (
        "A bot development framework with friendly APIs, session control and plugin-supported."
    )
    """melobot 项目描述

       :meta hide-value:
    """

    PROJ_SRC: str = "https://github.com/Meloland/melobot"
    """melobot 项目地址

       :meta hide-value:
    """

    ARGV: list[str] = sys.argv
    """当前运行的 argv

       :meta hide-value:
    """

    OS_NAME: str = os.name
    """当前系统名称

       :meta hide-value:
    """

    PLATFORM: str = sys.platform
    """当前系统平台

       :meta hide-value:
    """

    PY_VER: str = sys.version
    """当前 python 版本

       :meta hide-value:
    """

    PY_INFO: "sys._version_info" = sys.version_info
    """当前 python 信息

       :meta hide-value:
    """

    OS_SEP: str = os.sep

    """当前系统路径分隔符号，如 win 平台下的 "\\"

       :meta hide-value:
    """

    PATH_SEP: str = os.pathsep

    """当前系统路径间的分隔符号，如 win 平台下的 ";"

       :meta hide-value:
    """

    LINE_SEP: str = os.linesep

    """当前系统行尾序列，如 win 平台下的 "\\r\\n"

       :meta hide-value:
    """

    ENV: os._Environ[str] = os.environ
    """当前运行的环境变量

       :meta hide-value:
    """

    @classmethod
    def get_all(cls) -> dict[str, Any]:
        """以字典形式获取所有元信息

        :return: 包含所有元信息的，属性名为键的字典
        """
        return {k: v for k, v in cls.__dict__.items() if not k.startswith("__")}


MELOBOT_LOGO = r"""  __  __      _       ____        _
 |  \/  | ___| | ___ | __ )  ___ | |_
 | |\/| |/ _ \ |/ _ \|  _ \ / _ \| __|
 | |  | |  __/ | (_) | |_) | (_) | |_
 |_|  |_|\___|_|\___/|____/ \___/ \__|
"""
MELOBOT_LOGO_LEN = max(len(_) for _ in MELOBOT_LOGO.split("\n"))
