import asyncio
from enum import Enum

from .exceptions import BotHookError
from .log import get_ctx_logger
from .typing import Any, AsyncCallable, Generic, Iterable, TypeVar

HookEnum_T = TypeVar("HookEnum_T", bound=Enum)


class HookRunner(Generic[HookEnum_T]):
    """bot hook 运行器"""

    def __init__(self, type: HookEnum_T, func: AsyncCallable[..., None]) -> None:
        self.type = type
        self.callback = func

    async def run(self, *args: Any, **kwargs: Any) -> None:
        try:
            await self.callback(*args, **kwargs)
        except Exception:
            logger = get_ctx_logger()
            logger.error(f"bot 生命周期 hook 方法 {self.callback} 发生异常")
            logger.exc(locals=locals())


class HookBus(Generic[HookEnum_T]):
    def __init__(
        self, type: type[HookEnum_T], required: Iterable[HookEnum_T] | None = None
    ) -> None:
        self._store: dict[HookEnum_T, list[HookRunner]] = {t: [] for t in list(type)}
        self._required: set[HookEnum_T] = set(required) if required is not None else set()

    def register(
        self, hook_type: HookEnum_T, hook_func: AsyncCallable[..., None]
    ) -> None:
        runner = HookRunner(hook_type, hook_func)
        self._store[hook_type].append(runner)

    async def emit(
        self,
        hook_type: HookEnum_T,
        wait: bool = False,
        *,
        args: tuple | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> None:
        args = args if args is not None else ()
        kwargs = kwargs if kwargs is not None else {}

        tasks = [
            asyncio.create_task(runner.run(*args, **kwargs))
            for runner in self._store[hook_type]
        ]
        if hook_type in self._required and not len(tasks):
            raise BotHookError(f"对于 {hook_type} 类型的钩子，必须至少指定一个钩子方法")

        if wait and len(tasks):
            await asyncio.wait(tasks)
