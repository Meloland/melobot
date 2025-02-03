import asyncio
import time
from enum import Enum

from typing_extensions import Any, Callable, Generic, TypeVar

from .ctx import LoggerCtx
from .di import inject_deps
from .log.base import LogLevel
from .typ.base import AsyncCallable, P

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
        hook_func: AsyncCallable[..., None],
        once: bool = True,
    ) -> None:
        runner = HookRunner(hook_type, hook_func, once)
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
        if wait and len(tasks):
            await asyncio.wait(tasks)


class Hookable(Generic[HookEnumT]):
    def __init__(self, hook_type: type[HookEnumT], tag: str | None = None):
        super().__init__()
        self._hook_bus = HookBus[HookEnumT](hook_type, tag)

    def on(
        self, *periods: HookEnumT
    ) -> Callable[[AsyncCallable[P, None]], AsyncCallable[P, None]]:
        """注册一个 hook

        :param periods: 要绑定的 hook 类型
        :return: 装饰器
        """

        def hook_register_wrapped(func: AsyncCallable[P, None]) -> AsyncCallable[P, None]:
            for type in periods:
                self._hook_bus.register(type, func)
            return func

        return hook_register_wrapped
