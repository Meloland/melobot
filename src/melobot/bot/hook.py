import asyncio as aio
from functools import partial

from ..types.abc import BotHookRunnerArgs, BotLife
from ..types.exceptions import *
from ..types.tools import get_rich_str
from ..types.typing import *

if TYPE_CHECKING:
    from ..plugin.init import Plugin
    from ..utils.logger import BotLogger


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

    def __init__(self) -> None:
        self.store: Dict[BotLife, List[HookRunner]] = {
            v: [] for k, v in BotLife.__members__.items()
        }
        self.logger: "BotLogger"

    def _bind(self, logger: "BotLogger") -> None:
        self.logger = logger

    def _register(
        self,
        hook_type: BotLife,
        hook_func: Callable[..., Coroutine[Any, Any, None]],
        plugin: "Plugin",
    ) -> None:
        """
        注册一个生命周期运行器。由 plugin build 过程调用
        """
        if hook_type not in self.store.keys():
            raise BotHookError(
                f"尝试添加一个生命周期 hook 方法，但是其指定的类型 {hook_type} 不存在"
            )
        runner = HookRunner(hook_type, hook_func, plugin)
        self.store[hook_type].append(runner)

    async def _run_on_ctx(self, runner: HookRunner, *args, **kwargs) -> None:
        try:
            await runner.cb(*args, **kwargs)
        except Exception as e:
            func_name = runner._func.__qualname__
            pre_str = "插件 " + runner._plugin.ID if runner._plugin else "动态注册的"
            self.logger.error(f"{pre_str} hook 方法 {func_name} 发生异常")
            self.logger.error("异常回溯栈：\n" + get_better_exc(e))
            self.logger.error("异常点局部变量：\n" + get_rich_str(locals()))

    def on(self, hook_type: BotLife):
        def make_args(
            hook_func: Callable[..., Coroutine[Any, Any, None]]
        ) -> BotHookRunnerArgs:
            if not aio.iscoroutinefunction(hook_func):
                raise PluginBuildError(f"hook 方法 {hook_func.__name__} 必须为异步函数")
            return BotHookRunnerArgs(func=hook_func, type=hook_type)

        return make_args

    async def emit(
        self, hook_type: BotLife, *args, wait: bool = False, **kwargs
    ) -> None:
        """
        触发一个生命周期事件。如果指定 wait 为 True，则会等待所有生命周期 hook 方法完成
        """
        if not wait:
            for runner in self.store[hook_type]:
                aio.create_task(self._run_on_ctx(runner, *args, **kwargs))
        else:
            for runner in self.store[hook_type]:
                await self._run_on_ctx(runner, *args, **kwargs)
