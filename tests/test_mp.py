import asyncio
from functools import partial
from multiprocessing import SimpleQueue
from pathlib import Path

from melobot._render import get_rich_repr
from melobot.mp import MP_MODULE_NAME, PBox, Process, ProcessPool, ProcessPoolExecutor
from tests.base import *
from tests.mp.mod import simple_test

EMPTY_ENTRY_PATH = Path(__file__).parent.joinpath("mp", "empty.py").resolve()
MOD_PATH = Path(__file__).parent.joinpath("mp", "mod.py").resolve()
SUBMOD_PATH = Path(__file__).parent.joinpath("mp", "submod.py").resolve()
SUBMOD2_PATH = Path(__file__).parent.joinpath("mp", "submod2.py").resolve()
ARGV = ["123", "456"]
SIGNAL_QUEUE = SimpleQueue()
TEST_S = "/abc/123, '123456' <test>(123)45678900012"


async def test_single_process():
    name = f"{test_single_process.__name__}-p"
    p = Process(MOD_PATH, ARGV, PBox(simple_test, entry=MOD_PATH), name=name)
    p.start()
    p.join()
    assert p.exitcode == 0

    p = Process(
        MOD_PATH,
        ARGV,
        PBox(name="test_all", entry=MOD_PATH),
        name=name,
        args=(ARGV, MP_MODULE_NAME),
    )
    p.start()
    p.join()
    assert p.exitcode == 0

    p = Process(MOD_PATH, ARGV, print, name=name, args=(partial(get_rich_repr, TEST_S),))
    p.start()
    p.join()
    assert p.exitcode == 0

    p = Process(
        MOD_PATH,
        ARGV,
        print,
        name=name,
        args=(PBox(get_rich_repr, module="melobot._render"), TEST_S),
    )
    p.start()
    p.join()
    assert p.exitcode == 0


async def test_process_pool():
    func = PBox(name="sync_get_sum", entry=SUBMOD_PATH)
    with ProcessPool(entry=SUBMOD_PATH, argv=ARGV, processes=2) as pool:
        results = pool.map(func, range(1000, 2000, 200))
        assert results == [500500, 720600, 980700, 1280800, 1620900]

        ares = pool.apply_async(func, (2000,))
        res = ares.get(timeout=10)
        assert res == 2001000
        pool.terminate()


async def test_process_pool_executor():
    func = PBox(name="get_rich_str", module="mp.submod2", entry=SUBMOD2_PATH)
    with ProcessPoolExecutor(entry=EMPTY_ENTRY_PATH, max_workers=4) as pool:
        loop = asyncio.get_running_loop()
        res = await asyncio.gather(
            *tuple(loop.run_in_executor(pool, func, TEST_S) for _ in range(10))
        )
        pool.shutdown(wait=False)
    assert res[0][-1] == TEST_S
