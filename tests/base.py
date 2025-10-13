import asyncio as aio
import os
from contextlib import asynccontextmanager

import pytest as pt
import pytest_asyncio as ptaio
from pytest import fixture
from pytest_asyncio import fixture as aiofixture

from melobot._render import EXC_SHOW_INTERNAL
from melobot.log import Logger, LogLevel, set_global_logger
from melobot.log.report import set_loop_exc_log

os.environ[EXC_SHOW_INTERNAL] = "1"
set_global_logger(Logger("tests", level=LogLevel.DEBUG))
set_loop_exc_log(strict=True)
# Auto use "package" loop_scope (not pytest fixture scope) for all async test functions
pytestmark = pt.mark.asyncio(loop_scope="package")


@asynccontextmanager
async def loop_manager():
    from melobot import _run

    self_tasks = []
    manager = _run._MANAGER
    manager.started = True
    for hook in manager.started_hooks:
        hook()
    try:
        yield self_tasks
    finally:
        loop = aio.get_running_loop()
        try:
            manager.closed = True
            for hook in manager.closed_hooks:
                hook()

            to_cancel = aio.all_tasks(loop)
            to_cancel = to_cancel - set(self_tasks)
            if to_cancel:
                for task in to_cancel:
                    if task not in manager.immunity_tasks:
                        task.cancel()
                await aio.gather(*to_cancel, return_exceptions=True)

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
        finally:
            loop.set_exception_handler(None)
            manager._prepare_next_works()
