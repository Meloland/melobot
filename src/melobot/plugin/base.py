from typing import Iterable, final

from ..handle.base import EventHandler
from ..handle.process import Flow
from ..typ import BetterABC, Callable, abstractattr
from .ipc import AsyncShare, SyncShare


class Plugin(BetterABC):
    """插件基类，子类需要把以下属性按 :func:`.abstractattr` 的要求实现"""

    version: str = abstractattr()
    """插件版本

       :meta hide-value:
    """

    shares: Iterable[SyncShare | AsyncShare] = ()
    """插件共享对象

       :meta hide-value:
    """

    funcs: Iterable[Callable] = ()
    """插件导出函数

       :meta hide-value:
    """

    flows: Iterable[Flow] = ()
    """插件处理流

       :meta hide-value:
    """

    desc: str = ""
    """插件的短描述信息

       :meta hide-value:
    """

    docs: str = ""
    """插件的长描述信息

       :meta hide-value:
    """

    keywords: list[str] = []
    """插件的分类关键词

       :meta hide-value:
    """

    url: str = ""
    """插件的项目主页

       :meta hide-value:
    """

    author: str = ""
    """插件作者

       :meta hide-value:
    """

    def __init__(self) -> None:
        super().__init__()
        self.name: str
        self.handlers: tuple[EventHandler, ...]

    @final
    def __plugin_build__(self, name: str) -> None:
        self.name = name
        self.handlers = tuple(EventHandler(self, flow) for flow in self.flows)
