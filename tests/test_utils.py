# -*- encoding: utf-8 -*-
# @File   : test_utils.py
# @Time   : 2024/08/26 20:53:04
# @Author : Kariko Lin

import asyncio
from enum import Enum
from random import choice, randint

from typing_extensions import Any, Coroutine

from melobot.utils import *
from tests.base import *


async def test_singleton() -> None:
    @singleton
    class ChlorideP:
        def __init__(self, sign: Any) -> None:
            self.sign = sign

        def __str__(self) -> str:
            return f"Chloride with sign: {self.sign}"

    a, b = ChlorideP("nya"), ChlorideP("rua")
    assert a is b and b.sign == a.sign


# Interesting names :)
# Try to search them in some places
ESTHER_EGGS = [
    "PedroDelMar",
    "ElapsingDreams",
    "ShimakazeProject",
    "MelorenAe",
    "aiCoreIn",
    "MelodyEcho",
    "SnowyKami",
    "LiteeCiallo",
    "DislinkSforza",
]


class TestRwc:
    RWC = RWContext(10)
    EGGS = ESTHER_EGGS.copy()
    BUF = EGGS.copy()
    READING_FLAGS = [False for _ in range(len(EGGS))]
    ASYNC_READED = False

    @classmethod
    async def write(cls) -> None:
        async with cls.RWC.write():
            i = randint(0, len(TestRwc.EGGS) - 1)
            val = cls.BUF[i]
            if val == "":
                raise ValueError("写写冲突")

            cls.BUF[i] = ""
            await aio.sleep(0.01)
            cls.BUF[i] = val

    @classmethod
    async def read(cls) -> None:
        async with cls.RWC.read():
            i = randint(0, len(TestRwc.EGGS) - 1)
            val = cls.BUF[i]
            if val == "":
                raise ValueError("读写冲突")
            if cls.READING_FLAGS[i]:
                cls.ASYNC_READED = True

            cls.READING_FLAGS[i] = True
            await aio.sleep(0.01)
            cls.READING_FLAGS[i] = False

    @classmethod
    async def test_rwcontrol(cls) -> None:
        # Ensure concurrent reading be encountered in task seqs
        r_seq = [cls.read() for _ in range(5)]

        # Avoid GC complaint that caused by unclosed coroutine
        getters = [cls.read, cls.write]
        rw_seq = [getters[choice([0, 1])]() for _ in range(50)]

        idx = choice(range(0, len(r_seq) + len(rw_seq) - 1))
        seq = rw_seq[:idx] + r_seq + rw_seq[idx:]
        await aio.wait(map(aio.create_task, seq))
        assert cls.ASYNC_READED


async def test_get_id() -> None:
    n = 100000
    ids = [get_id() for _ in range(n)]
    assert n - len(set(ids)) <= 1


class TestAsyncInterfaceAdapter:
    async def f1() -> None: ...

    def f2() -> int:
        return 1

    async def f3() -> int:
        return 1

    @classmethod
    def f4(cls) -> Coroutine[None, None, int]:
        return cls.f3()

    f5 = lambda: TestAsyncInterfaceAdapter.f3()

    async def f6(x: int, y: int) -> int:
        return x + y

    @classmethod
    async def test_to_async(cls) -> None:
        assert to_async(cls.f1) is cls.f1

        ret = await to_async(cls.f2)()
        assert ret == 1

        ret = await to_async(cls.f3)()
        assert ret == 1

        ret = await to_async(cls.f4)()
        assert ret == 1

        ret = await to_async(cls.f5)()
        assert ret == 1

    @classmethod
    async def test_to_coro(cls) -> None:
        coro = cls.f1()
        assert to_coro(coro) is coro
        coro.close()

        ret = await to_coro(cls.f2)
        assert ret == 1

        ret = await to_coro(cls.f3)
        assert ret == 1

        ret = await to_coro(cls.f4)
        assert ret == 1

        ret = await to_coro(cls.f5)
        assert ret == 1

        ret = await to_coro(cls.f6, 1, y=2)
        assert ret == 3


class TestIfNot:
    REJECTED = False
    RET = 0

    @classmethod
    def restore(cls) -> None:
        cls.REJECTED = False
        cls.RET = 0

    @classmethod
    async def reject(cls) -> None:
        cls.REJECTED = True

    @staticmethod
    async def get_cond() -> bool:
        return False

    @classmethod
    async def test_if_not(cls) -> None:
        async def func() -> None:
            cls.RET = 1

        f1 = if_not(condition=cls.get_cond, reject=cls.reject, give_up=True)(func)
        await f1()
        assert cls.REJECTED
        assert cls.RET == 0

        cls.restore()

        f2 = if_not(condition=cls.get_cond, reject=cls.reject, give_up=False)(func)
        await f2()
        assert cls.REJECTED
        assert cls.RET == 1


class TestUnfoldCtx:
    VAL = 0

    class SyncCtx:
        def __enter__(self) -> None:
            TestUnfoldCtx.VAL = 1

        def __exit__(self, *_, **__) -> None:
            TestUnfoldCtx.VAL = 0

    class AsyncCtx:
        async def __aenter__(self) -> None:
            TestUnfoldCtx.VAL = 1

        async def __aexit__(self, *_, **__) -> None:
            TestUnfoldCtx.VAL = 0

    @classmethod
    async def test_unfold_ctx(cls) -> None:
        async def func() -> None:
            assert cls.VAL == 1

        f = unfold_ctx(cls.SyncCtx)(func)
        await f()
        assert cls.VAL == 0
        f = unfold_ctx(cls.AsyncCtx)(func)
        await f()
        assert cls.VAL == 0


class Status(Enum):
    TOO_MANY_REQUESTS = 1
    REQUEST_TIMEOUT = 2
    EXPECTATION_FAILED = 3
    OK = 4


class TestAsyncUtils:
    NYA = ""

    async def lock_callback(self) -> int:
        return Status.TOO_MANY_REQUESTS

    async def time_callback(self) -> int:
        return Status.REQUEST_TIMEOUT

    async def cd_callback(self, timeout: float) -> int:
        return Status.TOO_MANY_REQUESTS

    async def test_lock(self) -> None:
        @lock(self.lock_callback)
        async def gen_ini_string() -> int:  # using NYA
            if not TestAsyncUtils.NYA:
                TestAsyncUtils.NYA += f"[{choice(ESTHER_EGGS)}]\n"
            await aio.sleep(0)
            TestAsyncUtils.NYA += f"clsid = {get_id()}"
            return Status.OK

        coropool = [gen_ini_string() for _ in ESTHER_EGGS]
        rets = await aio.gather(*coropool)
        assert rets.count(Status.OK) == 1

    async def test_cooldown(self) -> None:
        @cooldown(cd_callback=self.cd_callback, interval=3)
        async def sendmsg() -> int:
            # print(f"I'm searching {choice(ESTHER_EGGS)} in melobot group.")
            return Status.OK

        pool = [sendmsg() for _ in range(5)]
        rets = await aio.gather(*pool)
        assert rets.count(Status.TOO_MANY_REQUESTS) > 0

    async def test_semaphore(self) -> None:
        tickets = 10

        @semaphore(value=1)
        async def buyticket() -> int:
            nonlocal tickets
            if tickets <= 0:
                return Status.EXPECTATION_FAILED
            tickets -= 1
            return Status.OK

        pool = [buyticket() for _ in range(11)]
        rets = await aio.gather(*pool)
        assert not tickets and Status.EXPECTATION_FAILED in rets

    async def test_timelimit(self) -> None:
        @timelimit(self.time_callback, timeout=0.25)
        async def foo() -> int:
            await aio.sleep(0.5)
            return Status.OK

        ret = await foo()
        assert (await foo()) == Status.REQUEST_TIMEOUT

    async def test_speedlimit(self) -> None:
        """In my opinion, just name it 'chancelimit'."""

        @speedlimit(self.lock_callback, limit=1, duration=5)
        async def foo() -> int:
            await aio.sleep(0)
            return Status.OK

        pool = [foo() for _ in range(10)]
        rets = await aio.gather(*pool)
        assert rets.count(Status.OK) <= 1


class TimeGetter:
    def __get__(self, *_, **__) -> float:
        return aio.get_event_loop().time()


class TestCallableDispatch:
    # Use a descriptor as dynamic class var
    time = TimeGetter()
    TEST_ATTR = "__only_for_test__"

    @staticmethod
    def foo(e: aio.Event) -> None:
        e.set()

    @staticmethod
    async def afoo(e: aio.Event) -> None:
        await aio.sleep(0)
        e.set()

    @classmethod
    async def abar(cls, obj: Any) -> None:
        if not hasattr(obj, cls.TEST_ATTR):
            setattr(obj, cls.TEST_ATTR, 0)
        setattr(obj, cls.TEST_ATTR, getattr(obj, cls.TEST_ATTR) + 1)

    @classmethod
    async def test_call_later(cls) -> None:
        e = aio.Event()
        call_later(lambda: cls.foo(e), 0.1)
        begin = cls.time
        await e.wait()
        assert cls.time - begin <= 0.2

    @classmethod
    async def test_call_at(cls) -> None:
        e = aio.Event()
        call_at(lambda: cls.foo(e), cls.time + 0.1)
        begin = cls.time
        await e.wait()
        assert cls.time - begin <= 0.2

    @classmethod
    async def test_async_later(cls) -> None:
        e = aio.Event()
        await async_later(cls.afoo(e), 0.1)
        begin = cls.time
        await e.wait()
        assert cls.time - begin <= 0.1

    @classmethod
    async def test_async_at(cls) -> None:
        e = aio.Event()
        await async_at(cls.afoo(e), cls.time + 0.1)
        begin = cls.time
        await e.wait()
        assert cls.time - begin <= 0.1

    @classmethod
    async def test_async_interval(cls) -> None:
        obj = type("__XXX", (object,), {})()
        t = async_interval(lambda: cls.abar(obj), 0.1)
        await aio.sleep(0.5)
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass
        assert getattr(obj, cls.TEST_ATTR) >= 3
