import asyncio as aio
import os
import time
import traceback
from asyncio import iscoroutinefunction
from copy import deepcopy
from functools import partial
from pathlib import Path
from types import MethodType

from ..context.session import SESSION_LOCAL, BotSessionManager
from ..meta import MODULE_MODE_FLAG, MODULE_MODE_SET
from ..types.abc import BotHookRunnerArgs, BotLife
from ..types.exceptions import *
from ..types.typing import *

if TYPE_CHECKING:
    from ..init import MeloBot
    from ..utils.config import BotConfig
    from ..utils.logger import Logger
    from .plugin import Plugin


class HookRunner:
    """
    bot 生命周期 hook 方法
    """

    def __init__(
        self,
        type: str,
        func: Callable[..., Coroutine[Any, Any, None]],
        plugin: Optional["Plugin"],
    ) -> None:
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
    __logger: "Logger"

    @classmethod
    def _bind(cls, logger: "Logger") -> None:
        """
        初始化该类，绑定全局日志器和行为响应器
        """
        cls.__logger = logger

    @classmethod
    def _register(cls, hook_type: BotLife, runner: HookRunner) -> None:
        """
        注册一个生命周期运行器。由 plugin build 过程调用
        """
        if hook_type not in cls.__store__.keys():
            raise BotHookError(
                f"尝试添加一个生命周期 hook 方法，但是其指定的类型 {hook_type} 不存在"
            )
        cls.__store__[hook_type].append(runner)

    @classmethod
    def on(
        cls, hook_type: BotLife, callback: Callable[..., Coroutine[Any, Any, None]]
    ) -> None:
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
        session = BotSessionManager.make_empty()
        token = SESSION_LOCAL._add_ctx(session)
        try:
            await runner.cb(*args, **kwargs)
        except Exception as e:
            e_name = e.__class__.__name__
            func_name = runner._func.__qualname__
            pre_str = "插件" + runner._plugin.ID if runner._plugin else "动态注册的"
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
        触发一个生命周期事件。如果指定 wait 为 True，则会等待所有生命周期 hook 方法完成
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

    def __init__(
        self,
        id: str,
        ver: str,
        path: Path,
        share_objs: list[tuple[str, str]],
        signal_methods: list[tuple[str, str]],
    ) -> None:
        self.id = id
        self.version = ver
        self.path = path
        self.shares = share_objs
        self.signal_methods = signal_methods


class BotProxy:
    """
    外部使用的 Bot 对象
    """

    def __init__(self) -> None:
        self.__origin__: "MeloBot"

    def _bind(self, bot_origin: "MeloBot") -> None:
        self.__origin__ = bot_origin

    @property
    def is_activate(self) -> bool:
        return not self.__origin__.slack

    def get_loop(self) -> aio.AbstractEventLoop:
        """
        获得运行 bot 的异步事件循环
        """
        return self.__origin__.loop

    def get_logger(self) -> "Logger":
        """
        获得 bot 全局日志器
        """
        return self.__origin__.logger

    def get_config(self) -> "BotConfig":
        """
        获得 bot 全局配置
        """
        return deepcopy(self.__origin__.config)

    def get_plugins(self) -> Dict[str, PluginProxy]:
        """
        获取 bot 当前所有插件信息
        """
        return {id: plugin._proxy for id, plugin in self.__origin__.plugins.items()}

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
        return self.get_loop.call_later(delay, callback)

    def call_at(self, callback: partial, timestamp: float):
        """
        在指定的时间戳后调度一个 callback 执行。注意这个 callback 应该是同步方法

        当 timestamp <= 当前时刻将立即执行
        """
        if timestamp <= time.time():
            return self.get_loop.call_soon(callback)
        else:
            return self.get_loop.call_later(timestamp - time.time(), callback)

    def async_later(
        self,
        callback: Coroutine[Any, Any, Any],
        delay: float,
        exit_cb: Coroutine[Any, Any, None] = None,
    ) -> aio.Future:
        """
        在指定的 delay 后调度一个 callback 执行。注意这个 callback 应该是协程。
        返回一个 future 对象，可用于等待结果。可以指定 exit_cb 用于在被迫 cancel 时调用
        """

        async def async_cb(fut: aio.Future) -> Any:
            try:
                await aio.sleep(delay)
                res = await callback
                fut.set_result(res)
            except aio.CancelledError:
                if exit_cb is not None:
                    await exit_cb
                callback.close()

        fut = aio.Future()
        aio.create_task(async_cb(fut))
        return fut

    def async_at(
        self,
        callback: Coroutine[Any, Any, Any],
        timestamp: float,
        exit_cb: Coroutine[Any, Any, None] = None,
    ) -> aio.Future:
        """
        在指定的 timestamp 调度一个 callback 执行。注意这个 callback 应该是协程。
        返回一个 future 对象，可用于等待结果。可以指定 exit_cb 用于在被迫 cancel 时调用

        当 timestamp <= 当前时刻将立即执行
        """
        if timestamp <= time.time():
            return self.async_later(callback, 0, exit_cb)
        else:
            return self.async_later(callback, timestamp - time.time(), exit_cb)

    def async_interval(
        self,
        callback: Callable[[None], Coroutine[Any, Any, None]],
        interval: float,
        exit_cb: Coroutine[Any, Any, None] = None,
    ) -> aio.Task:
        """
        以指定的 interval 调度一个回调执行。callback 是协程产生器。
        返回一个 task 对象用于取消回调。可以指定 exit_cb 用于在被迫 cancel 时调用
        """

        async def interval_cb():
            try:
                while True:
                    coro = callback()
                    await aio.sleep(interval)
                    await coro
            except aio.CancelledError:
                if exit_cb is not None:
                    await exit_cb
                coro.close()

        t = aio.create_task(interval_cb())
        return t

    def on(
        self,
        hook_type: BotLife,
        callback: Callable[..., Coroutine[Any, Any, None]] = None,
    ):
        """
        用作装饰器，不传入 callback 参数，即可注册一个 bot 生命周期 hook 方法。

        也可直接调用此方法，传入 callback 参数来注册一个 hook 方法。
        callback 可以是类实例方法，也可以不是。callback 如果是类实例方法，请自行包裹为一个 partial 函数。

        例如你的插件类是：`A`，而你需要传递一个类实例方法：`A.xxx`，
        那么你的 callback 参数就应该是：`functools.partial(A.xxx, self)`
        """

        def make_args(
            func: Callable[..., Coroutine[Any, Any, None]]
        ) -> BotHookRunnerArgs:
            return BotHookRunnerArgs(func=func, type=hook_type)

        if callback is None:
            return make_args
        else:
            BotHookBus.on(hook_type, callback)

    def on_all_loaded(self):
        """
        用作装饰器，可注册一个 LOADED 生命周期 hook 方法
        """
        return self.on(BotLife.LOADED, None)

    def on_connected(self):
        """
        用作装饰器，可注册一个 CONNECTED 生命周期 hook 方法
        """
        return self.on(BotLife.CONNECTED, None)

    def on_before_close(self):
        """
        用作装饰器，可注册一个 BEFORE_CLOSE 生命周期 hook 方法
        """
        return self.on(BotLife.BEFORE_CLOSE, None)

    def on_before_stop(self):
        """
        用作装饰器，可注册一个 BEFORE_STOP 生命周期 hook 方法
        """
        return self.on(BotLife.BEFORE_STOP, None)

    def on_event_built(self):
        """
        用作装饰器，可注册一个 EVENT_BUILT 生命周期 hook 方法
        """
        return self.on(BotLife.EVENT_BUILT, None)

    def on_action_presend(self):
        """
        用作装饰器，可注册一个 ACTION_PRESEND 生命周期 hook 方法
        """
        return self.on(BotLife.ACTION_PRESEND, None)


BOT_PROXY = BotProxy()
