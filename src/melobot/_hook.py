import asyncio
from enum import Enum
from typing import Any, Generic, TypeVar

from .ctx import LoggerCtx
from .di import inject_deps
from .log.base import LogLevel
from .typ import AsyncCallable

HookEnumT = TypeVar("HookEnumT", bound=Enum)


class HookRunner(Generic[HookEnumT]):
    """bot hook 运行器"""

    def __init__(self, type: HookEnumT, func: AsyncCallable[..., None]) -> None:
        self.type = type
        self.callback: AsyncCallable[..., None] = inject_deps(func, manual_arg=True)

    async def run(self, *args: Any, **kwargs: Any) -> None:
        try:
            await self.callback(*args, **kwargs)
        except Exception:
            logger = LoggerCtx().get()
            logger.exception(
                f"生命周期阶段 {self.type} 的 hook 方法 {self.callback} 发生异常"
            )
            logger.generic_obj("异常点局部变量：", locals(), level=LogLevel.ERROR)


class HookBus(Generic[HookEnumT]):
    def __init__(self, type: type[HookEnumT]) -> None:
        self._store: dict[HookEnumT, list[HookRunner]] = {t: [] for t in list(type)}

    def register(self, hook_type: HookEnumT, hook_func: AsyncCallable[..., None]) -> None:
        runner = HookRunner(hook_type, hook_func)
        self._store[hook_type].append(runner)

    async def emit(
        self,
        hook_type: HookEnumT,
        wait: bool = False,
        *,
        args: tuple | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> None:
        args = args if args is not None else ()
        kwargs = kwargs if kwargs is not None else {}
        logger = LoggerCtx().get()
        logger.debug(f"<{hook_type}> 阶段的 hook 开始（{wait = }）")  # noqa: E251, E202

        tasks = [
            asyncio.create_task(runner.run(*args, **kwargs))
            for runner in self._store[hook_type]
        ]
        if wait and len(tasks):
            await asyncio.wait(tasks)

        logger.debug(f"<{hook_type}> 阶段的 hook 已完成（{wait = }）")  # noqa: E251, E202
