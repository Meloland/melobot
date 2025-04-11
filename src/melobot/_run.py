from __future__ import annotations

import asyncio
import os
import signal
import sys
from weakref import WeakSet

from typing_extensions import Any, Callable, Coroutine, NoReturn

from ._lazy import singleton, singleton_clear
from .typ._enum import ExitCode

CLI_RUN_FLAG = "MELOBOT_CLI_RUN"
CLI_RUN_ALIVE_FLAG = "MELOBOT_CLI_RUN_ALIVE"
CLI_LAST_EXIT_CODE = "MELOBOT_CLI_LAST_EXIT_CODE"


@singleton
class LoopManager:
    def __init__(self) -> None:
        self.root_task: asyncio.Task | None = None

        self.started = False
        self.closed = False
        self.stop_accepted = False
        self._next_manager: LoopManager

        self.started_hooks: set[Callable[[], Any]] = set()
        self.closed_hooks: set[Callable[[], Any]] = set()
        self.immunity_tasks: WeakSet[asyncio.Task] = WeakSet()

    def run(self, root: Coroutine[Any, Any, None], debug: bool) -> None:
        try:
            # TODO: 在升级最低支持到 3.11 后，考虑更换为 new_event_loop，并使用 asyncio.Runner 来运行
            loop = asyncio.get_event_loop()
            asyncio.get_event_loop_policy().set_event_loop(loop)

            # TODO: 在升级最低支持到 3.12 后，设置为默认标准
            if sys.version_info >= (3, 12):
                loop.set_task_factory(asyncio.eager_task_factory)

            loop.set_debug(debug)
            loop.add_signal_handler(signal.SIGINT, self.stop)
            loop.add_signal_handler(signal.SIGTERM, self.stop)
            if sys.platform == "win32":
                loop.add_signal_handler(signal.SIGBREAK, self.stop)

            main = self._loop_main(root)
            loop.run_until_complete(main)

        except asyncio.CancelledError:
            pass

        finally:
            try:
                self._loop_cancel_all(loop)
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.run_until_complete(loop.shutdown_default_executor())
            finally:
                loop.set_exception_handler(None)
                asyncio.get_event_loop_policy().set_event_loop(None)
                loop.close()
                self._prepare_next_works()

    def _prepare_next_works(self) -> None:
        global _MANAGER
        singleton_clear(self)
        _MANAGER = LoopManager()
        _MANAGER.__dict__.update(self._next_manager.__dict__)
        _MANAGER._next_manager = _MANAGER.__class__()

    async def _loop_main(self, root: Coroutine[Any, Any, None]) -> None:
        self.started = True
        self.root_task = asyncio.create_task(root)
        for hook in self.started_hooks:
            hook()

        if CLI_RUN_FLAG in os.environ:
            while True:
                if self.stop_accepted or self.root_task.done():
                    break
                if not os.path.exists(os.environ[CLI_RUN_ALIVE_FLAG]):
                    self.root_task.cancel()
                    break
                await asyncio.sleep(0.45)
        else:
            await self.root_task

    def _loop_cancel_all(self, loop: asyncio.AbstractEventLoop) -> None:
        self.closed = True
        for hook in self.closed_hooks:
            hook()

        to_cancel = asyncio.all_tasks(loop)
        if not to_cancel:
            return
        for task in to_cancel:
            if task not in self.immunity_tasks:
                task.cancel()
        loop.run_until_complete(asyncio.tasks.gather(*to_cancel, return_exceptions=True))

        for task in to_cancel:
            if task.cancelled():
                continue
            if task.exception() is not None:
                loop.call_exception_handler(
                    {
                        "message": "事件循环关闭时，抛出未捕获的异常",
                        "exception": task.exception(),
                        "task": task,
                    }
                )

    def stop(self, *_: Any, **__: Any) -> None:
        if self.stop_accepted:
            return
        self.stop_accepted = True
        if self.root_task is not None:
            self.root_task.cancel()

    def restart(self) -> NoReturn:
        sys.exit(ExitCode.RESTART.value)

    def is_from_restart(self) -> bool:
        return (
            CLI_LAST_EXIT_CODE in os.environ
            and int(os.environ[CLI_LAST_EXIT_CODE]) == ExitCode.RESTART.value
        )

    def is_restartable(self) -> bool:
        if CLI_RUN_FLAG in os.environ:
            return True
        return False


_MANAGER = LoopManager()
_MANAGER._next_manager = _MANAGER.__class__()


def register_loop_started_hook(func: Callable[[], Any], allow_next: bool = False) -> None:
    if _MANAGER.started and not _MANAGER.closed:
        raise RuntimeError("事件循环正在运行，无法添加新的事件循环启动 hook")
    if _MANAGER.closed:
        if allow_next:
            _MANAGER._next_manager.started_hooks.add(func)
        else:
            raise RuntimeError("事件循环已关闭，无法添加新的事件循环启动 hook")
    _MANAGER.started_hooks.add(func)


def register_loop_closed_hook(func: Callable[[], Any], allow_next: bool = False) -> None:
    if _MANAGER.closed:
        if allow_next:
            _MANAGER._next_manager.closed_hooks.add(func)
        else:
            raise RuntimeError("事件循环已关闭，无法添加新的事件循环关闭 hook")
    _MANAGER.closed_hooks.add(func)


def add_immunity_task(task: asyncio.Task) -> asyncio.Task:
    if _MANAGER.closed:
        raise RuntimeError("事件循环已关闭，无法添加新的取消豁免任务")
    _MANAGER.immunity_tasks.add(task)
    return task


def is_async_running() -> bool:
    return _MANAGER.started and not _MANAGER.closed


def set_loop_exc_handler(
    exc_handler: Callable[[asyncio.AbstractEventLoop, dict[str, Any]], Any],
) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        register_loop_started_hook(
            lambda: asyncio.get_running_loop().set_exception_handler(exc_handler)
        )
    else:
        loop.set_exception_handler(exc_handler)
