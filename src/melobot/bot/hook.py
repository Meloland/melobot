import asyncio

from ..base.abc import BotLife
from ..base.exceptions import BotValueError
from ..base.typing import TYPE_CHECKING, Any, AsyncCallable

if TYPE_CHECKING:
    from ..utils.logger import BotLogger


class HookRunner:
    """bot hook 运行器"""

    def __init__(self, type: BotLife, func: AsyncCallable[..., None]) -> None:
        self.cb: AsyncCallable[..., None] = func
        self.type: BotLife = type


class BotHookBus:
    """bot hook 总线"""

    def __init__(self) -> None:
        self.store: dict[BotLife, list[HookRunner]] = {
            v: [] for v in BotLife.__members__.values()
        }
        self.logger: "BotLogger"

    def _bind(self, logger: "BotLogger") -> None:
        self.logger = logger

    def register(self, hook_type: BotLife, hook_func: AsyncCallable[..., None]) -> None:
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
            self.logger.exc(locals=locals())

    async def emit(
        self, hook_type: BotLife, *args: Any, wait: bool = False, **kwargs: Any
    ) -> None:
        tasks = []
        for runner in self.store[hook_type]:
            task = asyncio.create_task(self._run_on_ctx(runner, *args, **kwargs))
            tasks.append(task)

        if wait and len(tasks):
            await asyncio.wait(tasks)
