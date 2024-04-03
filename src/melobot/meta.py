import os
import sys
from typing import Any


class MetaInfo:
    """元信息类

    .. admonition:: 提示
       :class: tip

       一般无需手动实例化该类，多数情况会直接使用本类对象，或将本类用作类型注解。
    """

    def __init__(self) -> None:
        #: melobot 版本
        self.VER: str = "2.5.10"
        #: melobot 项目名称
        self.PROJ_NAME: str = "melobot"
        #: melobot 项目描述
        self.PROJ_DESC: str = (
            "A qq bot development framework with friendly APIs, session control and plugin-supported."
        )
        #: melobot 项目地址
        self.PROJ_SRC: str = "https://github.com/aicorein/melobot"
        #: melobot 项目作者
        self.AUTHOR: str = "aicorein"
        #: melobot 项目作者邮箱
        self.AUTHOR_EMAIL: str = "melodyecho@glowmem.com"
        #: 当前运行的 argv
        self.ARGV: list[str] = sys.argv
        #: 当前系统平台
        self.PLATFORM: str = sys.platform
        #: 当前 python 版本
        self.PY_VER: str = sys.version
        #: 当前 python 信息
        self.PY_INFO: sys._version_info = sys.version_info
        #: 当前系统路径分隔符号，如 win 平台下的 "\\"
        self.OS_SEP: str = os.sep
        #: 当前系统路径间的分隔符号，如 win 平台下的 ";"
        self.PATH_SEP: str = os.pathsep
        #: 当前系统行尾序列，如 win 平台下的 "\\r\\n"
        self.LINE_SEP: str = os.linesep
        #: 当前运行的环境变量
        self.ENV: os._Environ[str] = os.environ

    def get_all(self) -> dict[str, Any]:
        """以字典形式获取所有元信息

        :return: 包含所有元信息的，属性名为键的字典
        """
        return dict(self.__dict__.items())


MELOBOT_LOGO = r"""  __  __      _       ____        _
 |  \/  | ___| | ___ | __ )  ___ | |_
 | |\/| |/ _ \ |/ _ \|  _ \ / _ \| __|
 | |  | |  __/ | (_) | |_) | (_) | |_
 |_|  |_|\___|_|\___/|____/ \___/ \__|
"""
MELOBOT_LOGO_LEN = max(len(_) for _ in MELOBOT_LOGO.split("\n"))
