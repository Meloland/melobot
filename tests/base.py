import asyncio as aio
from contextlib import contextmanager

import pytest as pt
import pytest_asyncio as ptaio
from pytest import fixture
from pytest_asyncio import fixture as aiofixture

# Auto use "package" loop_scope (not pytest fixture scope) for all async test functions
pytestmark = pt.mark.asyncio(loop_scope="package")


@contextmanager
def loop_manager():
    from melobot import _run
    from melobot._lazy import singleton_clear

    manager = _run._MANAGER
    manager.started = True
    for hook in manager.started_hooks:
        hook()
    try:
        yield
    finally:
        manager.closed = True
        for hook in manager.closed_hooks:
            hook()
        singleton_clear(_run._MANAGER)
        _run._MANAGER = _run.LoopManager()
