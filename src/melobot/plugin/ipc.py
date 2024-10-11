from typing import Callable, Generic

from ..di import inject_deps
from ..exceptions import PluginIpcError
from ..typ import AsyncCallable, T
from ..utils import AttrsReprable, Locatable, RWContext


class AsyncShare(Generic[T], Locatable, AttrsReprable):
    """异步共享对象"""

    def __init__(
        self,
        name: str,
        reflector: AsyncCallable[[], T] | None = None,
        callabck: AsyncCallable[[T], None] | None = None,
        static: bool = False,
    ) -> None:
        """初始化异步共享对象

        :param name: 异步共享对象的名称
        :param reflector: 获取共享值的异步可调用方法
        :param callabck: 修改共享值的异步可调用方法
        :param static: 是否使用静态模式
        """
        super().__init__()
        self.name = name
        self.__safe_ctx = RWContext()
        self.__reflect: AsyncCallable[[], T] | None = (
            inject_deps(reflector) if reflector is not None else None
        )
        self.__callback: AsyncCallable[[T], None] | None = (
            inject_deps(callabck, manual_arg=True) if callabck is not None else None
        )
        self.static = static

        if self.name.startswith("_"):
            raise PluginIpcError(f"共享对象 {self} 的名称不能以 _ 开头")
        if self.static and self.__callback is not None:
            raise PluginIpcError(
                f"{self} 作为静态的共享对象，不能绑定用于更新值的回调方法"
            )

    def __call__(self, func: AsyncCallable[[], T]) -> AsyncCallable[[], T]:
        """绑定获取共享值的异步方法的装饰器，如果未在初始化时绑定

        :param func: 被绑定的异步可调用方法
        :return: `func` 原值
        """
        if self.__reflect is not None:
            raise PluginIpcError("共享对象已经有获取值的反射方法，不能再次绑定")
        self.__reflect = inject_deps(func)
        return func

    def setter(self, func: AsyncCallable[[T], None]) -> AsyncCallable[[T], None]:
        """绑定修改共享值的异步方法的装饰器，如果未在初始化时绑定

        :param func: 被绑定的异步可调用方法
        :return: `func` 原值
        """
        if self.static:
            raise PluginIpcError(
                f"{self} 作为静态的共享对象，不能绑定用于更新值的回调方法"
            )
        if self.__callback is not None:
            raise PluginIpcError("共享对象已经有更新值的回调方法，不能再次绑定")
        self.__callback = inject_deps(func, manual_arg=True)
        return func

    async def get(self) -> T:
        """获取异步共享值

        :return: 异步共享值
        """
        if self.__reflect is None:
            raise PluginIpcError("共享对象获取值的反射方法未绑定")
        async with self.__safe_ctx.read():
            return await self.__reflect()

    async def set(self, val: T) -> None:
        """设置异步共享值

        :param val: 新的异步共享值
        """
        if self.__callback is None:
            raise PluginIpcError("共享对象更新值的回调方法未绑定")
        async with self.__safe_ctx.write():
            return await self.__callback(val)


class SyncShare(Generic[T], Locatable, AttrsReprable):
    """同步共享对象"""

    def __init__(
        self,
        name: str,
        reflector: Callable[[], T] | None = None,
        callabck: Callable[[T], None] | None = None,
        static: bool = False,
    ) -> None:
        """初始化同步共享对象

        :param name: 同步共享对象的名称
        :param reflector: 获取共享值的可调用方法
        :param callabck: 修改共享值的可调用方法
        :param static: 是否使用静态模式
        """
        super().__init__()
        self.name = name
        self.__reflect = reflector
        self.__callback = callabck
        self.static = static

        if self.name.startswith("_"):
            raise PluginIpcError(f"共享对象 {self} 的名称不能以 _ 开头")
        if self.static and self.__callback is not None:
            raise PluginIpcError(
                f"{self} 作为静态的共享对象，不能绑定用于更新值的回调方法"
            )

    def __call__(self, func: Callable[[], T]) -> Callable[[], T]:
        """绑定获取共享值的方法的装饰器，如果未在初始化时绑定

        :param func: 被绑定的可调用方法
        :return: `func` 原值
        """
        if self.__reflect is not None:
            raise PluginIpcError("共享对象已经有获取值的反射方法，不能再次绑定")
        self.__reflect = func
        return func

    def setter(self, func: Callable[[T], None]) -> Callable[[T], None]:
        """绑定修改共享值的方法的装饰器，如果未在初始化时绑定

        :param func: 被绑定的可调用方法
        :return: `func` 原值
        """
        if self.static:
            raise PluginIpcError(
                f"{self} 作为静态的共享对象，不能绑定用于更新值的回调方法"
            )
        if self.__callback is not None:
            raise PluginIpcError("共享对象已经有更新值的回调方法，不能再次绑定")
        self.__callback = func
        return func

    def get(self) -> T:
        """获取共享值

        :return: 共享值
        """
        if self.__reflect is None:
            raise PluginIpcError("共享对象未绑定获取值的反射方法")
        return self.__reflect()

    def set(self, val: T) -> None:
        """设置共享值

        :param val: 新的共享值
        """
        if self.__callback is None:
            raise PluginIpcError("共享对象未绑定更新值的回调方法")
        self.__callback(val)


class IPCManager:
    def __init__(self) -> None:
        self._shares: dict[str, dict[str, AsyncShare | SyncShare]] = {}

    def add(self, plugin: str, obj: AsyncShare | SyncShare) -> None:
        objs = self._shares.setdefault(plugin, {})
        if objs.get(obj.name) is not None:
            raise PluginIpcError(f"插件 {plugin} 中已存在名为 {obj.name} 的共享对象")
        objs[obj.name] = obj

    def add_func(self, plugin: str, func: Callable) -> None:
        self.add(plugin, SyncShare(func.__name__, lambda: func, None, True))

    def get(self, plugin: str, id: str) -> AsyncShare | SyncShare:
        if (objs := self._shares.get(plugin)) is None:
            raise PluginIpcError(f"插件 {plugin} 不提供共享功能")
        if (obj := objs.get(id)) is None:
            raise PluginIpcError(f"无法获取不存在的共享对象：标识 {id} 不存在")
        return obj
