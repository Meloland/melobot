import asyncio as aio
import os
import time
import traceback
from asyncio import iscoroutinefunction
from functools import partial
from types import MethodType

from ..meta import MODULE_MODE_FLAG, MODULE_MODE_SET
from ..types.core import AbstractResponder
from ..types.exceptions import *
from ..types.models import BotLife, HookRunnerArgs
from ..types.typing import *
from ..types.utils import Logger
from ..utils.config import BotConfig
from .ipc import PluginStore, ShareObject
from .session import SESSION_LOCAL, BotSessionManager


class HookRunner:
    """
    bot 生命周期 hook 运行器
    """

    def __init__(self, type: str, func: Callable, plugin: Optional[object]) -> None:
        self._func = func
        self._plugin = plugin
        # 对应：绑定的 func 是插件类的实例方法
        if plugin:
            self.cb = partial(self._func, plugin)
        # 对应：绑定的 func 是普通函数
        else:
            self.cb = self._func
        self.type = type


class BotHookBus:
    """
    bot 生命周期 hook 总线
    """

    __store__: Dict[BotLife, List[HookRunner]] = {
        v: [] for k, v in BotLife.__members__.items()
    }
    __logger: Logger
    __responder: AbstractResponder

    @classmethod
    def _bind(cls, logger: Logger, responder: AbstractResponder) -> None:
        """
        初始化该类，绑定全局日志器和行为响应器
        """
        cls.__logger = logger
        cls.__responder = responder

    @classmethod
    def _register(cls, hook_type: BotLife, runner: HookRunner) -> None:
        """
        注册一个生命周期运行器。由 plugin build 过程调用
        """
        if hook_type not in cls.__store__.keys():
            raise BotHookError(
                f"尝试添加一个生命周期 hook，但是其指定的类型 {hook_type} 不存在"
            )
        cls.__store__[hook_type].append(runner)

    @classmethod
    def on(cls, hook_type: BotLife, callback: Callable) -> None:
        """
        动态注册 hook 方法
        """
        if isinstance(callback, HookRunner):
            raise BotHookError("已注册的生命周期 hook 方法不能再注册")
        if not iscoroutinefunction(callback):
            raise BotHookError(f"生命周期 hook 方法 {callback.__name__} 必须为异步函数")
        if (
            isinstance(callback, partial) and isinstance(callback.func, MethodType)
        ) or isinstance(callback, MethodType):
            raise BotHookError("callback 应该是 function，而不是 bound method")
        runner = HookRunner(hook_type, callback, plugin=None)
        cls._register(hook_type, runner)

    @classmethod
    async def _run_on_ctx(cls, runner: HookRunner, *args, **kwargs) -> None:
        session = BotSessionManager.make_empty(cls.__responder)
        token = SESSION_LOCAL._add_ctx(session)
        try:
            await runner.cb(*args, **kwargs)
        except Exception as e:
            e_name = e.__class__.__name__
            func_name = runner._func.__qualname__
            pre_str = (
                "插件" + runner._plugin.__class__.__id__
                if runner._plugin
                else "动态注册的"
            )
            cls.__logger.error(
                f"{pre_str} hook 方法 {func_name} 发生异常：[{e_name}] {e}"
            )
            cls.__logger.debug(f"生命周期 hook 方法的 args: {args} kwargs：{kwargs}")
            cls.__logger.debug("异常回溯栈：\n" + traceback.format_exc().strip("\n"))
        finally:
            SESSION_LOCAL._del_ctx(token)

    @classmethod
    async def emit(
        cls, hook_type: BotLife, *args, wait: bool = False, **kwargs
    ) -> None:
        """
        触发一个生命周期信号。如果指定 wait 为 True，则会等待所有生命周期 hook 方法完成
        """
        if not wait:
            for runner in cls.__store__[hook_type]:
                aio.create_task(cls._run_on_ctx(runner, *args, **kwargs))
        else:
            for runner in cls.__store__[hook_type]:
                await cls._run_on_ctx(runner, *args, **kwargs)


class PluginProxy:
    """
    bot 插件代理类。供外部使用
    """

    def __init__(self, plugin: object) -> None:
        self.id = plugin.__class__.__id__
        self.version = plugin.__class__.__version__
        self.root_path = plugin.__class__.ROOT
        self.share: Dict[str, ShareObject] = {}
        for property, namespace, id in plugin.__class__.__share__:
            self.share[id] = PluginStore.get(namespace, id)


class BotProxy:
    """
    外部使用的 Bot 对象
    """

    def __init__(self) -> None:
        self.__origin__: object

    def _bind(self, bot_origin: object) -> None:
        self.__origin__ = bot_origin

    @property
    def loop(self) -> aio.AbstractEventLoop:
        return self.__origin__.loop

    @property
    def logger(self) -> Logger:
        """
        bot 全局日志器
        """
        return self.__origin__.logger

    @property
    def config(self) -> BotConfig:
        """
        bot 全局配置
        """
        return self.__origin__.config

    @property
    def plugins(self) -> Dict[str, PluginProxy]:
        """
        获取 bot 当前所有插件信息
        """
        return {
            id: plugin._Plugin__proxy for id, plugin in self.__origin__.plugins.items()
        }

    @property
    def is_activate(self) -> bool:
        return not self.__origin__.slack

    def slack(self) -> None:
        """
        使 bot 不再发送 action。但 ACTION_PRESEND 钩子依然会触发
        """
        self.__origin__.slack = True

    def activate(self) -> None:
        """
        使 bot 可以发送 action
        """
        self.__origin__.slack = False

    async def close(self) -> None:
        """
        关闭 bot
        """
        await self.__origin__.close()

    def is_module_run(self) -> bool:
        """
        检查是否是模块运行模式
        """
        return os.environ.get(MODULE_MODE_FLAG) == MODULE_MODE_SET

    async def restart(self) -> None:
        """
        重启 bot。只可在模块运行模式下使用
        """
        await self.__origin__.restart()

    def call_later(self, callback: partial, delay: float):
        """
        在指定的 delay 后调度一个 callback 执行。注意这个 callback 应该是同步方法
        """
        return self.loop.call_later(delay, callback)

    def call_at(self, callback: partial, timestamp: float):
        """
        在指定的时间戳后调度一个 callback 执行。注意这个 callback 应该是同步方法

        当 timestamp <= 当前时刻将立即执行
        """
        if timestamp <= time.time():
            return self.loop.call_soon(callback)
        else:
            return self.loop.call_later(timestamp - time.time(), callback)

    def async_later(
        self, callback: Coroutine[Any, Any, Any], delay: float
    ) -> aio.Future:
        """
        在指定的 delay 后调度一个 callback 执行。注意这个 callback 应该是协程。
        返回一个 future 对象，可用于等待结果
        """

        async def async_cb(fut: aio.Future) -> Any:
            await aio.sleep(delay)
            res = await callback
            fut.set_result(res)

        fut = aio.Future()
        aio.create_task(async_cb(fut))
        return fut

    def async_at(
        self, callback: Coroutine[Any, Any, Any], timestamp: float
    ) -> aio.Future:
        """
        在指定的 timestamp 调度一个 callback 执行。注意这个 callback 应该是协程。
        返回一个 future 对象，可用于等待结果

        当 timestamp <= 当前时刻将立即执行
        """
        if timestamp <= time.time():
            return self.async_later(callback, 0)
        else:
            return self.async_later(callback, timestamp - time.time())

    def async_interval(
        self, cb_maker: Callable[[None], Coroutine[Any, Any, None]], interval: float
    ) -> aio.Task:
        """
        以指定的 interval 调度一个 callback 执行。cb_maker 是用于产生 callback 的协程产生器。
        返回一个 task 对象用于取消 callback
        """

        async def interval_cb():
            while True:
                await aio.sleep(interval)
                await cb_maker()

        t = aio.create_task(interval_cb())
        return t

    @classmethod
    def on(cls, hook_type: BotLife, callback: Callable = None):
        """
        用作装饰器，不传入 callback 参数，即可注册一个 bot 生命周期 hook。

        也可直接调用此方法，传入 callback 参数来注册一个 hook。
        callback 可以是类实例方法，也可以不是。callback 如果是类实例方法，请自行包裹为一个 partial 函数。

        例如你的插件类是：`A`，而你需要传递一个类实例方法：`A.xxx`，
        那么你的 callback 参数就应该是：`functools.partial(A.xxx, self)`
        """

        def make_args(func: AsyncFunc[None]) -> HookRunnerArgs:
            return HookRunnerArgs(func=func, type=hook_type)

        if callback is None:
            return make_args
        else:
            BotHookBus.on(hook_type, callback)


BOT_PROXY = BotProxy()
