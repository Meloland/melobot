import asyncio
import time
from asyncio import Task
from enum import Enum

from typing_extensions import Any, Generic, TypeVar

from .ctx import LoggerCtx
from .di import inject_deps
from .log.base import LogLevel
from .typ.base import AsyncCallable, SyncOrAsyncCallable
from .utils import to_async, to_sync

HookEnumT = TypeVar("HookEnumT", bound=Enum)


class HookRunner(Generic[HookEnumT]):
    def __init__(
        self, type: HookEnumT, func: AsyncCallable[..., None], once: bool = False
    ) -> None:
        self.type = type
        self.callback: AsyncCallable[..., None] = inject_deps(func, manual_arg=True)
        self.once = once
        self._valid = True
        self._lock = asyncio.Lock()

    async def _run(self, *args: Any, **kwargs: Any) -> None:
        try:
            await self.callback(*args, **kwargs)
        except Exception:
            logger = LoggerCtx().get()
            logger.exception(f"{self.type} 类型的 hook 方法 {self.callback} 发生异常")
            logger.generic_obj("异常点局部变量：", locals(), level=LogLevel.ERROR)

    async def run(self, *args: Any, **kwargs: Any) -> None:
        if not self._valid:
            return
        if not self.once:
            return await self._run(*args, **kwargs)

        async with self._lock:
            if not self._valid:
                return
            await self._run(*args, **kwargs)
            self._valid = False


class HookBus(Generic[HookEnumT]):
    def __init__(self, type: type[HookEnumT], tag: str | None = None) -> None:
        self._hooks: dict[HookEnumT, list[HookRunner]] = {t: [] for t in list(type)}
        self._stamps: dict[HookEnumT, float] = {}
        self._tag = tag

    def set_tag(self, tag: str | None) -> None:
        self._tag = tag

    def register(
        self,
        hook_type: HookEnumT,
        hook_func: SyncOrAsyncCallable[..., None],
        once: bool = True,
    ) -> None:
        runner = HookRunner(hook_type, to_async(hook_func), once)
        self._hooks[hook_type].append(runner)

    def get_evoke_time(self, hook_type: HookEnumT) -> float:
        return self._stamps.get(hook_type, -1)

    async def emit(
        self,
        hook_type: HookEnumT,
        wait: bool = False,
        /,
        *,
        args: tuple | None = None,
        kwargs: dict[str, Any] | None = None,
        callback: SyncOrAsyncCallable[[Task[None] | None], None] | None = None,
    ) -> None:
        self._stamps[hook_type] = time.time_ns() / 1e9
        args = args if args is not None else ()
        kwargs = kwargs if kwargs is not None else {}
        logger = LoggerCtx().get()

        msg = f"<{hook_type}>（{wait = }）"  # noqa: E251, E202
        if self._tag:
            msg = f"开始 {self._tag} 的 hook: {msg}"
        else:
            msg = f"开始 hook: {msg}"
        logger.debug(msg)

        tasks = tuple(
            asyncio.create_task(runner.run(*args, **kwargs))
            for runner in self._hooks[hook_type]
        )

        if callback is not None:
            if len(tasks):
                for t in tasks:
                    t.add_done_callback(to_sync(callback))
            else:
                to_sync(callback)(None)
                return

        if wait and len(tasks):
            await asyncio.wait(tasks)
