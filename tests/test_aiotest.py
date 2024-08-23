from tests.base import *


@fixture
def int_val():
    return 1


@aiofixture
async def test_v():
    return 5


async def test_loop(current_loop, int_val):
    assert int_val == 1
    assert current_loop is aio.get_running_loop()


async def test_loop2(current_loop, test_v):
    assert test_v == 5
    assert current_loop is aio.get_running_loop()


def test3(current_loop):
    assert isinstance(current_loop, aio.BaseEventLoop)
