from ..base import AttrsReprMixin, LocatableMixin
from ..exceptions import BotIpcError
from ..typing import AsyncCallable, Callable, Generic, T
from ..utils import RWContext


class AsyncShare(Generic[T], LocatableMixin, AttrsReprMixin):
    """异步共享对象"""

    def __init__(
        self,
        name: str,
        reflector: AsyncCallable[[], T] | None = None,
        callabck: AsyncCallable[[T], None] | None = None,
        static: bool = False,
    ) -> None:
        self.name = name
        self.__safe_ctx = RWContext()
        self.__reflect = reflector
        self.__callback = callabck
        self._static = static

    def __call__(self, func: AsyncCallable[[], T]) -> AsyncCallable[[], T]:
        if self.__reflect is not None:
            raise BotIpcError("共享对象已经有获取值的反射方法，不能再次绑定")
        self.__reflect = func
        return func

    def setter(self, func: AsyncCallable[[T], None]) -> AsyncCallable[[T], None]:
        if self.__callback is not None:
            raise BotIpcError("共享对象已经有更新值的回调方法，不能再次绑定")
        self.__callback = func
        return func

    async def get(self) -> T:
        if self.__reflect is None:
            raise BotIpcError("共享对象获取值的反射方法未绑定")
        async with self.__safe_ctx.read():
            return await self.__reflect()

    async def set(self, val: T) -> None:
        if self.__callback is None:
            raise BotIpcError("共享对象更新值的回调方法未绑定")
        async with self.__safe_ctx.write():
            return await self.__callback(val)


class SyncShare(Generic[T], LocatableMixin, AttrsReprMixin):
    """同步共享对象"""

    def __init__(
        self,
        name: str,
        reflector: Callable[[], T] | None = None,
        callabck: Callable[[T], None] | None = None,
        static: bool = False,
    ) -> None:
        self.name = name
        self.__reflect = reflector
        self.__callback = callabck
        self._static = static

    def __call__(self, func: Callable[[], T]) -> Callable[[], T]:
        if self.__reflect is not None:
            raise BotIpcError("共享对象已经有获取值的反射方法，不能再次绑定")
        self.__reflect = func
        return func

    def setter(self, func: Callable[[T], None]) -> Callable[[T], None]:
        if self.__callback is not None:
            raise BotIpcError("共享对象已经有更新值的回调方法，不能再次绑定")
        self.__callback = func
        return func

    def get(self) -> T:
        if self.__reflect is None:
            raise BotIpcError("共享对象未绑定获取值的反射方法")
        return self.__reflect()

    def set(self, val: T) -> None:
        if self.__callback is None:
            raise BotIpcError("共享对象未绑定更新值的回调方法")
        self.__callback(val)


class IPCManager:
    def __init__(self) -> None:
        self._shares: dict[str, dict[str, AsyncShare | SyncShare]] = {}

    def add(self, plugin: str, obj: AsyncShare | SyncShare) -> None:
        objs = self._shares.setdefault(plugin, {})
        if objs.get(obj.name) is not None:
            raise BotIpcError(f"插件 {plugin} 中已存在名为 {obj.name} 的共享对象")
        objs[obj.name] = obj

    def get(self, plugin: str, id: str) -> AsyncShare | SyncShare:
        if (objs := self._shares.get(plugin)) is None:
            raise BotIpcError(f"插件 {plugin} 中不存在名为 {id} 的共享对象")
        if (obj := objs.get(id)) is None:
            raise BotIpcError(f"无法获取不存在的共享对象：标识 {id} 不存在")
        return obj
