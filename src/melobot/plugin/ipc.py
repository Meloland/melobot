import asyncio

from ..base.abc import BaseLogger
from ..base.exceptions import BotIpcError
from ..base.tools import RWController
from ..base.typing import Any, AsyncCallable
from ..utils.logger import log_exc


class ShareObject:
    """共享对象"""

    def __init__(self, namespace: str, id: str) -> None:
        self.namespace = namespace
        self.id = id
        self.__rwc = RWController()
        self.__reflect: AsyncCallable[..., Any]
        self.__callback: AsyncCallable[..., Any]

        self.__cb_set = asyncio.Event()

    def _fill_ref(self, reflector: AsyncCallable[..., Any]) -> None:
        self.__reflect = reflector

    def _fill_cb(self, callback: AsyncCallable[..., Any]) -> None:
        self.__callback = callback
        self.__cb_set.set()

    @property
    async def val(self) -> Any:
        """共享对象引用的值"""
        async with self.__rwc.safe_read():
            return await self.__reflect()

    async def affect(self, *args: Any, **kwargs: Any) -> Any:
        """触发共享对象的回调，回调未设置时会等待。 如果本来就没有回调，则会陷入无休止等待"""
        await self.__cb_set.wait()
        async with self.__rwc.safe_write():
            return await self.__callback(*args, **kwargs)


class PluginStore:
    """插件共享存储"""

    def __init__(self) -> None:
        self.store: dict[str, dict[str, ShareObject]] = {}

    def create_so(
        self, reflector: AsyncCallable[..., Any], namespace: str, id: str
    ) -> None:
        """创建共享对象"""
        if namespace not in self.store.keys():
            self.store[namespace] = {}
        obj = self.store[namespace].get(id)
        if obj is not None:
            raise BotIpcError(
                f"已在 {namespace} 命名空间中注册标记为 {id} 的共享对象，拒绝再次注册"
            )
        obj = ShareObject(namespace, id)
        self.store[namespace][id] = obj
        obj._fill_ref(reflector)

    def bind_cb(self, namespace: str, id: str, cb: AsyncCallable[..., Any]) -> None:
        """为共享对象绑定回调"""
        if namespace not in self.store.keys():
            raise BotIpcError(f"共享对象回调指定的命名空间 {namespace} 不存在")
        if id not in self.store[namespace].keys():
            raise BotIpcError(
                f"共享对象回调指定的命名空间中，不存在标记为 {id} 的共享对象"
            )
        if self.store[namespace][id].__cb_set.is_set():
            raise BotIpcError(
                f"{namespace} 中标记为 {id} 的共享对象已被绑定过回调，拒绝再次绑定"
            )
        self.store[namespace][id]._fill_cb(cb)

    def get(self, namespace: str, id: str) -> ShareObject:
        """获取共享对象"""
        if namespace not in self.store.keys():
            raise BotIpcError(f"无法获取不存在的共享对象：命名空间 {namespace} 不存在")
        if id not in self.store[namespace].keys():
            raise BotIpcError(f"无法获取不存在的共享对象：标识 {id} 不存在")
        return self.store[namespace][id]


class PluginSignalHandler:
    """插件信号处理器"""

    def __init__(
        self, namespace: str, signal: str, func: AsyncCallable[..., Any]
    ) -> None:
        self.cb = func
        self.namespace = namespace
        self.signal = signal


class PluginBus:
    """插件信号总线"""

    def __init__(self) -> None:
        self.store: dict[str, dict[str, PluginSignalHandler]] = {}
        self.logger: BaseLogger

    def _bind(self, logger: BaseLogger) -> None:
        self.logger = logger

    def register(
        self, namespace: str, signal: str, func: AsyncCallable[..., Any]
    ) -> None:
        """绑定一个插件信号处理方法。由 plugin build 过程调用"""
        if namespace not in self.store.keys():
            self.store[namespace] = {}
        if signal in self.store[namespace].keys():
            raise BotIpcError("同一命名空间的同一信号只能绑定一个处理函数")
        self.store[namespace][signal] = PluginSignalHandler(namespace, signal, func)

    async def _run_on_ctx(
        self, handler: PluginSignalHandler, *args: Any, **kwargs: Any
    ) -> Any:
        """在指定的上下文下运行插件信号处理方法"""
        try:
            ret = await handler.cb(*args, **kwargs)
            return ret
        except Exception as e:
            func_name = handler.cb.__qualname__
            self.logger.error(f"插件信号处理方法 {func_name} 发生异常")
            log_exc(self.logger, locals(), e)

    async def emit(
        self, namespace: str, signal: str, *args: Any, wait: bool = False, **kwargs: Any
    ) -> Any:
        """触发一个插件信号。如果指定 wait 为 True，则会等待所有插件信号处理方法完成。 若启用 forward，则会将 会话
        从信号触发处转发到信号处理处。 但启用 forward，必须同时启用 wait。

        注意：如果你要等待返回结果，则需要指定 wait=True，否则不会等待且始终返回 None
        """
        if namespace not in self.store.keys():
            raise BotIpcError(f"插件信号命名空间 {namespace} 不存在，无法触发信号")
        if signal not in self.store[namespace].keys():
            self.logger.warning(
                f"命名空间 {namespace} 内，没有处理信号 {signal} 的处理函数"
            )
            return

        handler = self.store[namespace][signal]
        if not wait:
            asyncio.create_task(self._run_on_ctx(handler, *args, **kwargs))
            return None
        else:
            return await self._run_on_ctx(handler, *args, **kwargs)
