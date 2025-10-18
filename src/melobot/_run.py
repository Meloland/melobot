from __future__ import annotations

import asyncio
import inspect
import os
import signal
import sys
from contextlib import contextmanager
from weakref import WeakSet

from typing_extensions import Any, Callable, Coroutine, Generator, NoReturn

from ._lazy import singleton, singleton_clear
from .typ._enum import ExitCode
from .typ.base import T

CLI_RUN_FLAG = "MELOBOT_CLI_RUN"
CLI_RUN_ALIVE_FLAG = "MELOBOT_CLI_RUN_ALIVE"
CLI_LAST_EXIT_CODE = "MELOBOT_CLI_LAST_EXIT_CODE"


@singleton
class AsyncRunner:
    def __init__(self) -> None:
        self.root_task: asyncio.Task | None = None

        self.started = False
        self.closed = False
        self.stop_accepted = False
        self._loop_auto_set: bool = False
        self._started_in_loop: bool = False
        self._next_runner: AsyncRunner

        self.started_hooks: set[Callable[[], Any]] = set()
        self.closed_hooks: set[Callable[[], Any]] = set()
        self.immunity_tasks: WeakSet[asyncio.Task] = WeakSet()

    def run(
        self,
        coro: Coroutine[Any, Any, None],
        debug: bool,
        use_exc_handler: bool = True,
        loop_factory: Callable[[], asyncio.AbstractEventLoop] | None = None,
        eager_task: bool = True,
    ) -> None:
        self._run_check()

        # TODO: 在升级支持到 3.16 后，需要重新验证代码，
        # 因为 3.16 底层实现不再依赖于 policy，需要根据低级 loop 方法的新实现来调整
        if loop_factory is None:
            loop = asyncio.new_event_loop()
            if not self._loop_auto_set:
                asyncio.set_event_loop(loop)
                self._loop_auto_set = True
        else:
            loop = loop_factory()

        with self._loop_options(loop, debug, use_exc_handler, eager_task, None):
            try:
                main = self._loop_main(coro)
                loop.run_until_complete(main)
            except asyncio.CancelledError:
                pass
            except KeyboardInterrupt:
                pass
            finally:
                try:
                    self._cancel_all(loop)
                    loop.run_until_complete(loop.shutdown_asyncgens())
                    loop.run_until_complete(loop.shutdown_default_executor())
                finally:
                    if self._loop_auto_set:
                        asyncio.set_event_loop(None)
                    loop.close()
                    self._prepare_next_works()

    async def run_async(
        self,
        coro: Coroutine[Any, Any, None],
        reserved_tasks: set[asyncio.Task] | None = None,
        use_exc_handler: bool = True,
        pre_loop_sig_handlers: list[tuple[int, Callable[..., object]]] | None = None,
        shutdown_asyncgens: bool = False,
        shutdown_default_executor: bool = False,
    ) -> None:
        self._run_check()
        self._started_in_loop = True
        loop = asyncio.get_running_loop()

        with self._loop_options(loop, None, use_exc_handler, None, pre_loop_sig_handlers):
            try:
                await self._loop_main(coro)
            except asyncio.CancelledError:
                pass
            except KeyboardInterrupt:
                pass
            finally:
                try:
                    await self._cancel_all_async(loop, reserved_tasks)
                    if shutdown_asyncgens:
                        await loop.shutdown_asyncgens()
                    if shutdown_default_executor:
                        await loop.shutdown_default_executor()
                finally:
                    self._prepare_next_works()

    def _run_check(self) -> None:
        if self.closed:
            raise RuntimeError("运行器内的事件循环已关闭，此运行器无法再次运行")
        if self.started:
            raise RuntimeError("运行器内的事件循环已启动，无法再次运行")

    @contextmanager
    def _loop_options(
        self,
        loop: asyncio.AbstractEventLoop,
        debug: bool | None,
        set_exc_handler: bool | None,
        eager_task: bool | None,
        pre_loop_sig_handlers: list[tuple[int, Callable[..., object]]] | None,
    ) -> Generator[None, None, None]:
        if debug is not None:
            loop.set_debug(debug)
        if set_exc_handler:
            from .log.report import _log_loop_exception

            pre_exc_handler = loop.get_exception_handler()
            loop.set_exception_handler(_log_loop_exception)
        if eager_task:
            # TODO: 在升级最低支持到 3.12 后简化条件判断
            if sys.version_info >= (3, 12):
                loop.set_task_factory(asyncio.eager_task_factory)

        if sys.platform != "win32":
            loop.add_signal_handler(signal.SIGINT, self.stop)
            loop.add_signal_handler(signal.SIGTERM, self.stop)
            yield
            loop.remove_signal_handler(signal.SIGINT)
            loop.remove_signal_handler(signal.SIGTERM)
            if pre_loop_sig_handlers is not None:
                for sig, h in pre_loop_sig_handlers:
                    loop.add_signal_handler(sig, h)
        else:
            pre_signal_hs = (
                signal.getsignal(signal.SIGINT),
                signal.getsignal(signal.SIGTERM),
                signal.getsignal(signal.SIGBREAK),
            )
            signal.signal(signal.SIGINT, self.stop)
            signal.signal(signal.SIGTERM, self.stop)
            signal.signal(signal.SIGBREAK, self.stop)
            yield
            signal.signal(signal.SIGINT, pre_signal_hs[0])
            signal.signal(signal.SIGTERM, pre_signal_hs[1])
            signal.signal(signal.SIGBREAK, pre_signal_hs[2])

        if set_exc_handler:
            loop.set_exception_handler(pre_exc_handler)

    def _prepare_next_works(self) -> None:
        global _RUNNER
        singleton_clear(self)
        _RUNNER = AsyncRunner()
        _RUNNER.__dict__.update(self._next_runner.__dict__)
        _RUNNER._next_runner = _RUNNER.__class__()

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

    def _cancel_all(self, loop: asyncio.AbstractEventLoop) -> None:
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

    async def _cancel_all_async(
        self, loop: asyncio.AbstractEventLoop, reserved_tasks: set[asyncio.Task] | None = None
    ) -> None:
        self.closed = True
        for hook in self.closed_hooks:
            hook()

        to_cancel = asyncio.all_tasks(loop)
        cur_f = inspect.currentframe()
        f_set = set()
        f = cur_f
        while f is not None:
            f_set.add(f)
            f = f.f_back

        _need_cancel = set()
        for t in to_cancel:
            stack = t.get_stack(limit=1)
            if len(stack) and stack[0] in f_set:
                continue
            else:
                _need_cancel.add(t)
        to_cancel = _need_cancel - reserved_tasks if reserved_tasks else _need_cancel

        if not to_cancel:
            return
        for task in to_cancel:
            if task not in self.immunity_tasks:
                task.cancel()
        await asyncio.gather(*to_cancel, return_exceptions=True)

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
        if self.root_task is not None and not self.root_task.done():
            asyncio.get_running_loop().call_soon(self.root_task.cancel)

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


_RUNNER = AsyncRunner()
_RUNNER._next_runner = _RUNNER.__class__()


def register_started_hook(func: Callable[[], Any], allow_next: bool = False) -> None:
    if _RUNNER.started and not _RUNNER.closed:
        raise RuntimeError("异步运行器正在运行，无法添加新的启动 hook")
    if _RUNNER.closed:
        if allow_next:
            _RUNNER._next_runner.started_hooks.add(func)
        else:
            raise RuntimeError("异步运行器已关闭，无法添加新的启动 hook")
    _RUNNER.started_hooks.add(func)


def register_closed_hook(func: Callable[[], Any], allow_next: bool = False) -> None:
    if _RUNNER.closed:
        if allow_next:
            _RUNNER._next_runner.closed_hooks.add(func)
        else:
            raise RuntimeError("异步运行器已关闭，无法添加新的关闭 hook")
    _RUNNER.closed_hooks.add(func)


def create_immunity_task(
    coro: Coroutine[Any, Any, T],
) -> asyncio.Task[T]:
    if _RUNNER.closed:
        raise RuntimeError("异步运行器已关闭，无法添加新的取消豁免任务")
    if not _RUNNER.started:
        raise RuntimeError("异步运行器未启动，无法添加新的取消豁免任务")

    task = asyncio.create_task(coro)
    if _RUNNER._started_in_loop:
        # 当循环由外部创建时，我们无法保证任务的 cancel 不被调用
        # 因此直接替换 cancel 方法，确保其不会被取消
        task.cancel = lambda *_, **__: True  # type: ignore
    _RUNNER.immunity_tasks.add(task)
    return task


def is_runner_running() -> bool:
    return _RUNNER.started and not _RUNNER.closed
