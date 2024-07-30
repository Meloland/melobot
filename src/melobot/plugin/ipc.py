import asyncio
from dataclasses import dataclass

from ..exceptions import BotIpcError
from ..log import BotLogger
from ..typing import TYPE_CHECKING, Any, AsyncCallable, Callable, Generic, T
from ..utils import RWContext

if TYPE_CHECKING:
    from .base import Plugin


class AsyncShare(Generic[T]):
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


class SyncShare(Generic[T]):
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
            raise BotIpcError("共享对象获取值的反射方法未绑定")
        return self.__reflect()

    def set(self, val: T) -> None:
        if self.__callback is None:
            raise BotIpcError("共享对象更新值的回调方法未绑定")
        self.__callback(val)


@dataclass
class SignalHandler:
    plugin: "Plugin"
    signal: str
    cb: AsyncCallable[..., Any]


class IPCManager:
    def __init__(self, logger: BotLogger) -> None:
        self.shares: dict["Plugin", dict[str, AsyncShare | SyncShare]] = {}
        self.handlers: dict["Plugin", dict[str, SignalHandler]] = {}
        self.logger = logger

    def add_share(self, plugin: "Plugin", obj: AsyncShare | SyncShare) -> None:
        objs = self.shares.setdefault(plugin, {})
        if objs.get(obj.name) is not None:
            raise BotIpcError(f"插件 {plugin.name} 中已存在名为 {obj.name} 的共享对象")
        objs[obj.name] = obj

    def get_share(self, plugin: "Plugin", id: str) -> AsyncShare | SyncShare:
        if (objs := self.shares.get(plugin)) is None:
            raise BotIpcError(f"插件 {plugin.name} 中不存在名为 {id} 的共享对象")
        if (obj := objs.get(id)) is None:
            raise BotIpcError(f"无法获取不存在的共享对象：标识 {id} 不存在")
        return obj

    def register(self, handler: SignalHandler) -> None:
        """绑定一个插件信号处理方法"""
        handlers = self.handlers.setdefault(handler.plugin, {})
        if handlers.get(handler.signal) is not None:
            raise BotIpcError(
                f"插件 {handler.plugin.name} 中已存在名为 {handler.signal} 的信号处理方法"
            )
        handlers[handler.signal] = handler

    async def _handle_signal(
        self, handler: SignalHandler, *args: Any, **kwargs: Any
    ) -> Any:
        try:
            ret = await handler.cb(*args, **kwargs)
            return ret
        except Exception as e:
            func_name = handler.cb.__qualname__
            self.logger.error(
                f"插件 {handler.plugin.name} 的信号处理方法 {func_name} 发生异常"
            )
            self.logger.exc(locals=locals())

    async def emit(
        self, plugin: "Plugin", signal: str, *args: Any, wait: bool = False, **kwargs: Any
    ) -> Any:
        """
        触发一个插件信号。如果你要等待返回结果或等待信号处理方法完成，
        则需要指定 wait=True，否则不会等待且始终返回 None
        """
        if plugin not in self.handlers.keys():
            raise BotIpcError(f"插件 {plugin.name} 不存在信号处理方法，因此无法处理信号")
        if signal not in self.handlers[plugin].keys():
            raise BotIpcError(f"插件 {plugin.name} 内没有信号 {signal} 的处理方法")

        handler = self.handlers[plugin][signal]
        task = self._handle_signal(handler, *args, **kwargs)
        if not wait:
            asyncio.create_task(task)
            return None
        else:
            return await task
