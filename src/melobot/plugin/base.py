from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from typing_extensions import Callable, final, overload

from ..exceptions import PluginLoadError
from ..handle.base import Flow
from ..mixin import HookMixin
from ..typ.base import P, T
from .ipc import AsyncShare, SyncShare


class PluginLifeSpan(Enum):
    """插件生命周期的枚举"""

    INITED = "i"


@dataclass(frozen=True)
class PluginInfo:
    """插件信息类，用于添加描述信息"""

    version: str = ""
    desc: str = ""
    docs: Path | None = None
    keywords: list[str] | None = None
    url: str = ""
    author: str = ""


class PluginPlanner(HookMixin[PluginLifeSpan]):
    """插件管理器类

    用于声明一个插件，并为插件添加功能
    """

    def __init__(
        self,
        version: str,
        flows: list[Flow] | None = None,
        shares: list[SyncShare | AsyncShare] | None = None,
        funcs: list[Callable] | None = None,
        *,
        info: PluginInfo | None = None,
    ) -> None:
        """插件管理器初始化

        :param version: 版本号
        :param flows: 事件流列表。可以先指定为空，后续使用 :meth:`use` 绑定
        :param shares: 共享对象列表。可以先指定为空，后续使用 :meth:`use` 绑定
        :param funcs: 导出函数列表。可以先指定为空，后续使用 :meth:`use` 绑定
        :param info: 插件信息
        """
        super().__init__(hook_type=PluginLifeSpan)
        self.version = version
        self.init_flows = [] if flows is None else flows
        self.shares = [] if shares is None else shares
        self.funcs = [] if funcs is None else funcs
        self.info = PluginInfo() if info is None else info

        self._pname: str = ""
        self._built: bool = False
        self._plugin: Plugin

    @final
    def __p_build__(self, name: str) -> Plugin:
        if not self._built:
            self._pname = name
            self._hook_bus.set_tag(name)
            self._plugin = Plugin(self)
            self._built = True
        return self._plugin

    @overload
    def use(self, obj: Flow) -> Flow: ...
    @overload
    def use(self, obj: SyncShare[T]) -> SyncShare[T]: ...  # type: ignore[overload-overlap]
    @overload
    def use(self, obj: AsyncShare[T]) -> AsyncShare[T]: ...  # type: ignore[overload-overlap]
    @overload
    def use(self, obj: Callable[P, T]) -> Callable[P, T]: ...

    @final
    def use(self, obj: T) -> T:
        """装饰器

        绑定一个组件（流，共享对象，导出函数），标记插件创建后使用该组件。

        :param obj: 可用的组件
        :return: 被绑定的组件本身
        """
        if isinstance(obj, Flow):
            self.init_flows.append(obj)
        elif isinstance(obj, (SyncShare, AsyncShare)):
            self.shares.append(obj)
        elif callable(obj):
            self.funcs.append(obj)
        else:
            raise PluginLoadError(f"插件无法使用 {type(obj)} 类型的对象")
        return obj


class Plugin:
    def __init__(self, planner: PluginPlanner) -> None:
        self.planner = planner
        self.name = planner._pname
        self.hook_bus = planner._hook_bus

        self.shares = planner.shares
        self.funcs = planner.funcs
        self.init_flows = planner.init_flows
