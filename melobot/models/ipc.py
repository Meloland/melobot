import asyncio as aio
import traceback
from asyncio import iscoroutinefunction
from functools import partial
from types import MethodType

from ..interface.core import IActionResponder
from ..interface.exceptions import *
from ..interface.models import ShareCbArgs, SignalHandlerArgs
from ..interface.typing import *
from ..interface.utils import Logger
from .session import SESSION_LOCAL, BotSessionManager


class ShareObject:
    """
    共享对象
    """
    def __init__(self, namespace: str, id: str) -> None:
        self.__space__ = namespace
        self.__id__ = id
        self.__reflect__: Callable[[None], object] = lambda: None
        self.__callback__: Coroutine
        
        self.__cb_set__ = aio.Event()

    def _fill_ref(self, reflect_func: Callable[[None], object]) -> None:
        self.__reflect__ = reflect_func

    def _fill_cb(self, callback: Coroutine) -> None:
        self.__callback__ = callback
        self.__cb_set__.set()
    
    @property
    def val(self) -> Any:
        """
        共享对象引用的值
        """
        return self.__reflect__()
    
    async def affect(self, *args, **kwargs) -> Any:
        """
        触发共享对象的回调，回调未设置时会等待。
        如果本来就没有回调，则会陷入无休止等待
        """
        await self.__cb_set__.wait()
        return await self.__callback__(*args, **kwargs)


class PluginStore:
    """
    插件共享存储
    """
    __store__: Dict[str, Dict[str, ShareObject]] = {}

    @classmethod
    def _create_so(cls, property: Union[str, None], namespace: str, id: str, plugin: object) -> None:
        """
        创建共享对象。property 为 None 时，共享对象会引用到一个 None
        """
        if namespace not in cls.__store__.keys():
            cls.__store__[namespace] = {}
        obj = cls.__store__[namespace].get(id)
        if obj is None:
            obj = ShareObject(namespace, id)
            cls.__store__[namespace][id] = obj
        else:
            raise BotRuntimeError(f"命名空间 {namespace} 中已经存在 id 为 {id} 的共享对象")
        if property is not None:
            obj._fill_ref(lambda: getattr(plugin, property))
        else:
            obj._fill_ref(lambda: None)
    
    @classmethod
    def _bind_cb(cls, namespace: str, id: str, cb: AsyncFunc[Any], plugin: object) -> None:
        """
        为共享对象绑定回调
        """
        if namespace not in cls.__store__.keys():
            raise BotRuntimeError(f"共享对象回调指定的命名空间 {namespace} 不存在")
        if id not in cls.__store__[namespace].keys():
            raise BotRuntimeError(f"共享对象回调指定的命名空间中，不存在标记为 {id} 的共享对象")
        cls.__store__[namespace][id]._fill_cb(partial(cb, plugin))
    
    @classmethod
    def echo(cls, namespace: str, id: str) -> Callable:
        """
        为共享对象指定回调的装饰器，用于处理外部的 affect 请求。
        绑定为回调后，不提供异步安全担保
        """
        def bind_cb(cb: AsyncFunc[Any]) -> ShareCbArgs:
            return ShareCbArgs(namespace=namespace, id=id, cb=cb)
        return bind_cb
    
    @classmethod
    def get(cls, namespace: str, id: str) -> ShareObject:
        """
        获取共享对象，注意：共享对象不存在或暂时未初始化时会产生 None 引用。
        区别是前者会一直保持 None 引用，而后者则会随后绑定映射。
        但注意，除上述两种情况外，共享对象定义时也可引用到 None
        """
        if namespace not in cls.__store__.keys():
            cls.__store__[namespace] = {}
        if id not in cls.__store__[namespace].keys():
            cls.__store__[namespace][id] = ShareObject(namespace, id)
        return cls.__store__[namespace][id]


class PluginSignalHandler:
    """
    插件信号处理器
    """
    def __init__(self, type: str, func: Callable, plugin: Union[object, None]) -> None:
        self._func = func
        self._plugin = plugin
        # 对应：绑定的 func 是插件类的实例方法
        if plugin:
            self.cb = partial(self._func, plugin)
        # 对应：绑定的 func 是普通函数
        else:
            self.cb = self._func
        self.type = type


class PluginBus:
    """
    插件信号总线
    """
    __store__: Dict[str, List[PluginSignalHandler]] = {}
    __logger: Logger
    __responder: IActionResponder

    @classmethod
    def _bind(cls, logger: Logger, responder: IActionResponder) -> None:
        """
        初始化该类，绑定全局日志器和行为响应器
        """
        cls.__logger = logger
        cls.__responder = responder

    @classmethod
    def _register(cls, signal_name: str, handler: PluginSignalHandler) -> None:
        """
        注册一个插件信号处理方法。由 plugin build 过程调用
        """
        if signal_name not in cls.__store__.keys():
            cls.__store__[signal_name] = []
        cls.__store__[signal_name].append(handler)

    @classmethod
    def on(cls, signal_name: str, callback: Callable) -> None:
        """
        动态地注册信号处理方法。callback 可以是类实例方法，也可以不是。
        callback 如果是类实例方法，请自行包裹为一个 partial 函数。

        例如你的插件类是：`A`，而你需要传递一个类实例方法：`A.xxx`，
        那么你的 callback 参数就应该是：`functools.partial(A.xxx, self)`
        """
        if isinstance(callback, SignalHandlerArgs):
            raise BotRuntimeError("已注册的信号处理方法不能再注册")
        if not iscoroutinefunction(callback):
            raise BotTypeError(f"信号处理方法 {callback.__name__} 必须为异步函数")
        if (isinstance(callback, partial) and isinstance(callback.func, MethodType)) \
                or isinstance(callback, MethodType):
            raise BotTypeError("callback 应该是 function，而不是 bound method。")
        handler = PluginSignalHandler(signal_name, callback, plugin=None)
        cls._register(signal_name, handler)

    @classmethod
    async def _run_on_ctx(cls, handler: PluginSignalHandler, *args, forward: bool=False, **kwargs) -> None:
        """
        在指定的上下文下运行信号处理方法
        """
        if not forward:
            session = BotSessionManager.make_empty(cls.__responder)
            token = SESSION_LOCAL._add_ctx(session)
        try:
            await handler.cb(*args, **kwargs)
        except Exception as e:
            e_name = e.__class__.__name__
            func_name = handler._func.__qualname__
            pre_str = "插件" + handler._plugin.__class__.__id__ if handler._plugin else "动态注册的"
            cls.__logger.error(f"{pre_str} 信号处理方法 {func_name} 发生异常：[{e_name}] {e}")
            cls.__logger.debug(f"信号处理方法的 args: {args} kwargs：{kwargs}")
            cls.__logger.debug('异常回溯栈：\n' + traceback.format_exc().strip('\n'))
        finally:
            if not forward:
                SESSION_LOCAL._del_ctx(token)
    
    @classmethod
    async def emit(cls, signal_name: str, *args, wait: bool=False, forward: bool=False, **kwargs) -> None:
        """
        触发一个插件信号。如果指定 wait 为 True，则会等待所有信号处理方法完成。
        若启用 forward，则会将 session 从信号触发处转发到信号处理处。
        但启用 forward，必须同时启用 wait。
        """
        if forward and not wait:
            raise BotRuntimeError("在触发插件信号处理方法时传递原始 session，wait 参数需要为 True")
        if signal_name not in cls.__store__.keys():
            return
        if not wait:
            for handler in cls.__store__[signal_name]:
                aio.create_task(cls._run_on_ctx(handler, forward=forward, *args, **kwargs))
        else:
            for handler in cls.__store__[signal_name]:
                await cls._run_on_ctx(handler, forward=forward, *args, **kwargs)
