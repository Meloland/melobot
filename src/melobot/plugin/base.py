from enum import Enum
from typing import Iterable, final

from .._hook import HookBus
from ..handle.base import EventHandler
from ..handle.process import Flow
from ..typ import AsyncCallable, Callable, P, SingletonBetterABCMeta, abstractattr
from .ipc import AsyncShare, SyncShare


class PluginLifeSpan(Enum):
    """插件生命周期的枚举"""

    INITED = "i"


class Plugin(metaclass=SingletonBetterABCMeta):
    """插件基类

    子类需要把以下标记为抽象属性的属性，按 :func:`.abstractattr` 的要求实现，其余属性可选实现。
    """

    version: str = abstractattr()
    """插件版本（抽象属性）

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

    _hook_bus: HookBus[PluginLifeSpan]

    def __init__(self) -> None:
        self.name: str
        self.handlers: tuple[EventHandler, ...]
        self._built: bool = False

    @classmethod
    def __init_hook_bus__(cls, p_name: str | None = None) -> None:
        if not hasattr(cls, "_hook_bus"):
            cls._hook_bus = HookBus[PluginLifeSpan](PluginLifeSpan)
        cls._hook_bus.set_tag(p_name)

    @final
    def __plugin_build__(self, name: str) -> None:
        if not self._built:
            self.name = name
            self.__init_hook_bus__(name)
            self.handlers = tuple(EventHandler(self, flow) for flow in self.flows)
            self._built = True

    @classmethod
    def on(
        cls, *periods: PluginLifeSpan
    ) -> Callable[[AsyncCallable[P, None]], AsyncCallable[P, None]]:
        """注册一个 hook

        :param periods: 要绑定的 hook 类型
        :return: 装饰器
        """
        cls.__init_hook_bus__()

        def wrapped(func: AsyncCallable[P, None]) -> AsyncCallable[P, None]:
            for type in periods:
                cls._hook_bus.register(type, func)
            return func

        return wrapped
