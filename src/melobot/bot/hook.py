import asyncio

from ..base.abc import BaseLogger, BotLife
from ..base.exceptions import BotValueError
from ..base.tools import to_task
from ..base.typing import TYPE_CHECKING, Any, Callable, Coroutine
from ..utils.logger import log_exc


class HookRunner:
    """bot hook 运行器"""

    def __init__(
        self, type: BotLife, func: Callable[..., Coroutine[Any, Any, None]]
    ) -> None:
        self.cb: Callable[..., Coroutine[Any, Any, None]] = func
        self.type: BotLife = type


class BotHookBus:
    """bot hook 总线"""

    def __init__(self) -> None:
        self.store: dict[BotLife, list[HookRunner]] = {
            v: [] for k, v in BotLife.__members__.items()
        }
        self.logger: BaseLogger

    def _bind(self, logger: BaseLogger) -> None:
        self.logger = logger

    def register(
        self, hook_type: BotLife, hook_func: Callable[..., Coroutine[Any, Any, None]]
    ) -> None:
        if hook_type not in self.store.keys():
            raise BotValueError(
                f"尝试添加一个 bot 生命周期 hook 方法，但是其指定的类型 {hook_type} 不存在"
            )
        runner = HookRunner(hook_type, hook_func)
        self.store[hook_type].append(runner)

    async def _run_on_ctx(self, runner: HookRunner, *args: Any, **kwargs: Any) -> None:
        try:
            await runner.cb(*args, **kwargs)
        except Exception as e:
            func_name = runner.cb.__qualname__
            self.logger.error(f"bot 生命周期 hook 方法 {func_name} 发生异常")
            log_exc(self.logger, locals(), e)

    async def emit(
        self, hook_type: BotLife, *args: Any, wait: bool = False, **kwargs: Any
    ) -> None:
        if not wait:
            for runner in self.store[hook_type]:
                to_task(self._run_on_ctx(runner, *args, **kwargs))
        else:
            tasks = []
            for runner in self.store[hook_type]:
                tasks.append(to_task(self._run_on_ctx(runner, *args, **kwargs)))
            if len(tasks):
                await asyncio.wait(tasks)
