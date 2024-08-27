from tests.base import *


@fixture
def int_val() -> int:
    return 1


@aiofixture
async def test_v() -> int:
    return 5


async def test_loop(
    current_loop: aio.AbstractEventLoop, int_val: int
) -> None:
    assert int_val == 1
    assert current_loop is aio.get_running_loop()


async def test_loop2(
    current_loop: aio.AbstractEventLoop, test_v: int
) -> None:
    assert test_v == 5
    assert current_loop is aio.get_running_loop()


async def test3(current_loop: aio.AbstractEventLoop) -> None:
    assert isinstance(current_loop, aio.BaseEventLoop)
