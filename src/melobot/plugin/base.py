from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from typing_extensions import Callable, Iterable, final, overload

from ..exceptions import PluginLoadError
from ..handle.base import Flow
from ..mixin import HookMixin
from ..typ.base import AsyncCallable, P, SyncOrAsyncCallable, T
from .ipc import AsyncShare, SyncShare


class PluginLifeSpan(Enum):
    """插件生命周期的枚举"""

    INITED = "i"


@dataclass(frozen=True)
class PluginInfo:
    """插件信息类，用于添加描述信息"""

    desc: str = ""
    docs: Path | None = None
    keywords: tuple[str] | None = None
    url: str = ""
    author: str = ""


class PluginPlanner(HookMixin[PluginLifeSpan]):
    """插件管理器类

    用于声明一个插件，并为插件添加功能
    """

    def __init__(
        self,
        version: str,
        flows: Iterable[Flow] | None = None,
        shares: Iterable[SyncShare | AsyncShare] | None = None,
        funcs: Iterable[Callable] | None = None,
        auto_import: list[str] | bool = False,
        *,
        info: PluginInfo | None = None,
    ) -> None:
        """插件管理器初始化

        :param version: 版本号
        :param flows: 事件流。可以先指定为空，后续使用 :meth:`use` 绑定
        :param shares: 共享对象（需要在本插件内定义）。可以先指定空，后续用 :meth:`use` 绑定
        :param funcs: 导出函数（需要在本插件内定义，提供方法是未定义行为）。可以先指定空，后续用 :meth:`use` 绑定
        :param auto_import:
            需要自动导入的模块的路径列表（相对路径以插件目录为基准），该参数对动态插件无效。
            如果为 `True` 导入插件目录下所有模块，此时只会导入 `.py` 模块。
            如果你需要导入 `.{pyc,pyd,so,...}` 等其他可加载模块，请自行提供列表。自行提供列表时的一些提示：

            不要包含目录路径，这永远没有效果

            建议使用 :func:`glob.glob` 或 :meth:`pathlib.Path.glob` 方法获取路径，而不是手动拼接或查找

            一个模块在加载时，其向上到插件目录的所有父目录的 `__init__.{pyc,pyd,so,py...}` 都会被自动加载，
            此时不需要手动提供 `__init__.{pyc,pyd,so,py...}` 文件。加载时的扩展名优先级请查看 :data:`~melobot.MODULE_EXTS`
            （优先级从高到低，且与操作系统平台有关）

            如果一个目录中只有 `__init__.{pyc,pyd,so,py...}` 文件，此时只能手动提供

        :param info: 插件信息
        """
        super().__init__(hook_type=PluginLifeSpan)
        self.version = version
        self.init_flows = [] if flows is None else list(flows)
        self.shares = set[SyncShare | AsyncShare]() if shares is None else set(shares)
        self.funcs = set[Callable]() if funcs is None else set(funcs)
        self.info = PluginInfo() if info is None else info
        self.auto_import = auto_import

        self._pname: str = ""
        self._built: bool = False
        self._plugin: Plugin

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
            self.shares.add(obj)
        elif callable(obj):
            self.funcs.add(obj)
        else:
            raise PluginLoadError(f"插件无法使用 {type(obj)} 类型的对象")
        return obj

    @property
    def on_inited(self) -> Callable[[SyncOrAsyncCallable[P, None]], AsyncCallable[P, None]]:
        """给插件注册 :obj:`.PluginLifeSpan.INITED` 阶段 hook 的装饰器"""
        return self.on(PluginLifeSpan.INITED)


class Plugin:
    def __init__(self, planner: PluginPlanner) -> None:
        self.planner = planner
        self.name = planner._pname
        self.hook_bus = planner._hook_bus

        self.shares = planner.shares
        self.funcs = planner.funcs
        self.init_flows = planner.init_flows
