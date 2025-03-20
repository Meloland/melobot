from __future__ import annotations

import asyncio
import os
import signal
import sys
from enum import Enum

from typing_extensions import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Coroutine,
    NoReturn,
    NotRequired,
    TypedDict,
    cast,
)

from .log.base import GenericLogger, Logger, LogLevel

if TYPE_CHECKING:
    import socket

CLI_RUN_FLAG = "MELOBOT_CLI_RUN"
CLI_RUN_ALIVE_FLAG = "MELOBOT_CLI_RUN_ALIVE"
CLI_LAST_EXIT_CODE = "MELOBOT_CLI_LAST_EXIT_CODE"


class ExitCode(Enum):
    NORMAL = 0
    ERROR = 1
    RESTART = 2


class LoopManager:
    __instance__: LoopManager

    def __new__(cls, *_: Any, **__: Any) -> LoopManager:
        if not hasattr(cls, "__instance__"):
            cls.__instance__ = super().__new__(cls)
        return cls.__instance__

    def __init__(self, logger: GenericLogger) -> None:
        self.root_task: asyncio.Task | None = None
        self.stop_accepted = False
        self.logger: GenericLogger = logger
        self.exc_handler = ExceptionHandler(self, logger)
        self.strict_log = False

    def run(self, root: Coroutine[Any, Any, None], debug: bool, strict_log: bool) -> None:
        self.strict_log = strict_log
        try:
            loop = asyncio.get_event_loop()
            asyncio.get_event_loop_policy().set_event_loop(loop)
            loop.set_exception_handler(self.exc_handler.handle_from_loop)
            if debug is not None:
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

    async def _loop_main(self, root: Coroutine[Any, Any, None]) -> None:
        self.root_task = asyncio.create_task(root)

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
        to_cancel = asyncio.all_tasks(loop)
        if not to_cancel:
            return
        for task in to_cancel:
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


class LoopExcCtx(TypedDict):
    message: str
    exception: NotRequired[BaseException]
    future: NotRequired[asyncio.Future]
    task: NotRequired[asyncio.Task]
    handle: NotRequired[asyncio.Handle]
    protocol: NotRequired[asyncio.Protocol]
    transport: NotRequired[asyncio.Transport]
    socket: NotRequired["socket.socket"]
    asyncgen: NotRequired[AsyncGenerator]


class ExceptionHandler:
    def __init__(self, manager: LoopManager, logger: GenericLogger) -> None:
        self.mananger = manager
        self.logger = logger

    def handle_from_loop(self, loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
        strict_log = self.mananger.strict_log
        ctx = cast(LoopExcCtx, context)
        with_loop_ctx = {"loop": loop} | ctx
        exc = ctx.get("exception")
        msg = ctx["message"]

        if exc is not None:
            if (
                isinstance(exc, SystemExit)
                and exc.code is not None
                and int(exc.code) == ExitCode.RESTART.value
            ):
                self.logger.debug("收到重启信号，即将重启...")

            elif "exception was never retrieved" in msg:
                fut = ctx.get("future")
                task = ctx.get("task")
                if strict_log:
                    try:
                        raise exc
                    except BaseException:
                        self.logger.exception(f"从未捕获的异常的回溯栈：{msg}")
                self.logger.generic_obj(
                    f"发现从未捕获的异常（这不一定是错误）：{msg}",
                    {"future": fut, "task": task},
                    level=LogLevel.ERROR if strict_log else LogLevel.DEBUG,
                )

            else:
                try:
                    raise exc
                except BaseException:
                    self.logger.exception(f"事件循环中抛出预期外的异常：{msg}")
                    self.logger.generic_obj("相关变量信息：", with_loop_ctx, level=LogLevel.ERROR)

        else:
            self.logger.error(f"事件循环出现预期外的状况：{msg}")
            self.logger.generic_obj("相关变量信息：", with_loop_ctx, level=LogLevel.ERROR)

    def handle_from_report(self, exc: BaseException, msg: str, obj: Any = None) -> None:
        try:
            raise exc
        except BaseException:
            self.logger.exception(msg)
            if obj is not None:
                self.logger.generic_obj("相关变量信息：", obj, level=LogLevel.ERROR)


LOOP_MANAGER = LoopManager(Logger("melobot.loop", LogLevel.DEBUG))


def report_exc(exc: BaseException, msg: str, var: Any) -> None:
    LOOP_MANAGER.exc_handler.handle_from_report(exc, msg, var)
