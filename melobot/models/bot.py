import asyncio as aio
import traceback
from asyncio import iscoroutinefunction
from functools import partial
from types import MethodType

from .session import BotSessionManager,SESSION_LOCAL
from ..interface.core import IActionResponder
from ..interface.exceptions import *
from ..interface.models import BotLife, PluginProxy, HookRunnerArgs
from ..interface.typing import *
from ..interface.utils import Logger
from ..utils.config import BotConfig


class HookRunner:
    """
    bot 生命周期 hook 运行器
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


class BotHookBus:
    """
    bot 生命周期 hook 总线
    """
    __store: Dict[BotLife, List[HookRunner]] = \
        {v:[] for k, v in BotLife.__members__.items()}
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
    def _register(cls, hook_type: BotLife, runner: HookRunner) -> None:
        """
        注册一个生命周期运行器。由 plugin build 过程调用
        """
        if hook_type not in cls.__store.keys():
            raise BotException("尝试添加一个生命周期 hook，但是其类型不存在")
        cls.__store[hook_type].append(runner)

    @classmethod
    def on(cls, hook_type: BotLife, callback: Callable) -> None:
        """
        动态注册 hook 方法
        """
        if isinstance(callback, HookRunner):
            raise BotException("已注册的生命周期 hook 方法不能再注册")
        if not iscoroutinefunction(callback):
            raise BotException("生命周期 hook 方法必须为异步函数")
        if (isinstance(callback, partial) and isinstance(callback.func, MethodType)) \
                or isinstance(callback, MethodType):
            raise BotException("callback 应该是 function，而不是 bound method。")
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
            pre_str = "插件" + runner._plugin.id if runner._plugin else "动态注册的"
            cls.__logger.error(f"{pre_str} hook 方法 {func_name} 发生异常：[{e_name}] {e}")
            cls.__logger.debug(f"生命周期 hook 方法的 args: {args} kwargs：{kwargs}")
            cls.__logger.debug('异常回溯栈：\n' + traceback.format_exc().strip('\n'))
        finally:
            SESSION_LOCAL._del_ctx(token)

    @classmethod
    async def emit(cls, hook_type: BotLife, *args, wait: bool=False, **kwargs) -> None:
        """
        触发一个生命周期信号。如果指定 wait 为 True，则会等待所有生命周期 hook 方法完成
        """
        if hook_type not in cls.__store.keys():
            raise BotException("尝试触发一个生命周期信号，但是其类型不存在")
        if not wait:
            for runner in cls.__store[hook_type]:
                aio.create_task(cls._run_on_ctx(runner, *args, **kwargs))
        else:
            for runner in cls.__store[hook_type]:
                await cls._run_on_ctx(runner, *args, **kwargs)


class BotProxy:
    """
    外部使用的 Bot 对象
    """

    def __init__(self) -> None:
        self.__bot__: object

    def _bind(self, bot_origin: object) -> None:
        self.__bot__ = bot_origin

    @property
    def config(self) -> BotConfig:
        """
        bot 全局配置
        """
        return self.__bot__.config
    
    @property
    def logger(self) -> Logger:
        """
        bot 全局日志器
        """
        return self.__bot__.logger
    
    @property
    def plugins(self) -> List[PluginProxy]:
        """
        获取 bot 当前所有插件信息
        """
        return {id:plugin.proxy for id, plugin in self.__bot__.plugins.items()}
    
    def deactive(self) -> None:
        """
        使 bot 不再处理任何事件（元事件除外）
        """
        self.__bot__._dispatcher._slack = True
    
    def activate(self) -> None:
        """
        使 bot 开始处理事件
        """
        self.__bot__._dispatcher._slack = False
    
    async def close(self) -> None:
        """
        关闭 bot
        """
        await self.__bot__.close()
    
    @classmethod
    def on(cls, hook_type: BotLife, callback: Callable=None) -> None:
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
