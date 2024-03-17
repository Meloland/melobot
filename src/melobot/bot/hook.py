import asyncio as aio

from ..types.abc import BotLife
from ..types.exceptions import BotHookError, get_better_exc
from ..types.tools import get_rich_str
from ..types.typing import TYPE_CHECKING, Any, Callable, Coroutine

if TYPE_CHECKING:
    from ..utils.logger import Logger


class HookRunner:
    """
    bot 生命周期 hook 方法
    """

    def __init__(
        self, type: BotLife, func: Callable[..., Coroutine[Any, Any, None]]
    ) -> None:
        self.cb = func
        self.type = type


class BotHookBus:
    """
    bot 生命周期 hook 总线
    """

    def __init__(self) -> None:
        self.store: dict[BotLife, list[HookRunner]] = {
            v: [] for k, v in BotLife.__members__.items()
        }
        self.logger: "Logger"

    def _bind(self, logger: "Logger") -> None:
        self.logger = logger

    def register(
        self, hook_type: BotLife, hook_func: Callable[..., Coroutine[Any, Any, None]]
    ) -> None:
        """
        注册一个生命周期运行器。由 plugin build 过程调用
        """
        if hook_type not in self.store.keys():
            raise BotHookError(
                f"尝试添加一个生命周期 hook 方法，但是其指定的类型 {hook_type} 不存在"
            )
        runner = HookRunner(hook_type, hook_func)
        self.store[hook_type].append(runner)

    async def _run_on_ctx(self, runner: HookRunner, *args, **kwargs) -> None:
        try:
            await runner.cb(*args, **kwargs)
        except Exception as e:
            func_name = runner.cb.__qualname__
            self.logger.error(f"hook 方法 {func_name} 发生异常")
            self.logger.error("异常回溯栈：\n" + get_better_exc(e))
            self.logger.error("异常点局部变量：\n" + get_rich_str(locals()))

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
