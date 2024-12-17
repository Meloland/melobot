# -*- encoding: utf-8 -*-
# @File   : test_utils.py
# @Time   : 2024/08/26 20:53:04
# @Author : Kariko Lin

from http import HTTPStatus
from io import StringIO
from math import isclose
from random import randint, choice
from typing import Optional

from melobot.ctx import LoggerCtx
from melobot.log import Logger
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


# make sure the 2 readers below always get different results.
_ESTHER_EGGS = [
    'PedroDelMar', 'ElapsingDreams', 'ShimakazeProject',
    'MelorenAe', 'aiCoreIn', 'MelodyEcho',
    'SnowyKami', 'LiteeCiallo', 'DislinkSforza'
]


class TestTriggerCondition:
    RET_STR = HTTPStatus.PRECONDITION_REQUIRED

    # just a if-else trigger model
    # way better than RA2(
    async def rejection(self) -> None:
        pass

    # like trigger 0: [obj2] delayed init Power logic
    async def allow_powr_hint(self) -> bool:
        await aio.sleep(6)
        # sleep(6)
        return False  # i.e. the current value of a local var.

    # like trigger 1: [Stage2.Power] init with power hint
    async def test_condition_deco(self) -> None:
        @if_not(condition=self.allow_powr_hint, reject=self.rejection, give_up=True)
        async def hint_powr() -> None:
            TestTriggerCondition.RET_STR = HTTPStatus.OK
            # just leave out details not relative.

        await hint_powr()
        assert TestTriggerCondition.RET_STR == HTTPStatus.PRECONDITION_REQUIRED


# TODO: `unfold_ctx` decorator testing.
async def test_ctx_unfolding() -> None:
    ...


class TestRWContext:
    SHARED_BUFFER = [''] * 10
    RW_CONTROL = RWContext(10)

    esther_eggs = _ESTHER_EGGS + ['...']

    async def write_randomized(self) -> int:
        async with self.RW_CONTROL.write():
            idx = randint(0, 9)
            if self.SHARED_BUFFER[idx]:
                return HTTPStatus.INSUFFICIENT_STORAGE
            self.SHARED_BUFFER[idx] = choice(self.esther_eggs)
        return HTTPStatus.OK

    async def read_raw(self) -> str:
        async with self.RW_CONTROL.read():
            i = randint(0, 9)
            data = self.SHARED_BUFFER[i]
            if self.SHARED_BUFFER[i]:
                self.SHARED_BUFFER[i] = ''
        return data

    async def read_parsed(self) -> Optional[str]:
        async with self.RW_CONTROL.read():
            k = randint(0, 9)
            data = self.SHARED_BUFFER[k]
            if self.SHARED_BUFFER[k]:
                self.SHARED_BUFFER[k] = ''
        if not data or data == '...':
            return None
        buffer, word_cnt = '', 0
        for i in data:
            if i.islower() or i.isdigit():
                buffer += i
                continue
            word_cnt += 1
            if word_cnt > 1:
                break
            buffer += i
        return buffer

    async def test_rwcontrol(self) -> None:
        rwseq = [choice([
            self.write_randomized(),
            self.read_parsed(),
            self.read_raw()
        ]) for _ in range(50)]
        rets: list[int | Optional[str]] = await aio.gather(*rwseq)
        for i in rets:
            if isinstance(i, int):
                continue
            assert (
                i in self.esther_eggs  # read_raw
                or i is None  # read_parsed read empty cell.
                or len([j for j in i if j.isupper()]) <= 1)


# no need, since `get_id()` always use it.
# just check out the usages of `get_id()`, for the exception possibility.

# class TestSnowFlakeIdWorker:
#     ...


class TestAsyncUtils:
    NYA = ""

    async def lock_callback(self) -> int:
        return HTTPStatus.TOO_MANY_REQUESTS

    async def time_callback(self) -> int:
        return HTTPStatus.REQUEST_TIMEOUT

    async def cd_callback(self, timeout: float) -> int:
        return HTTPStatus.TOO_MANY_REQUESTS

    async def test_lock(self) -> None:
        @lock(self.lock_callback)
        async def gen_ini_string() -> int:  # using NYA
            if not TestAsyncUtils.NYA:
                TestAsyncUtils.NYA += f'[{choice(_ESTHER_EGGS)}]\n'
            await aio.sleep(0)
            TestAsyncUtils.NYA += f'clsid = {get_id()}'
            return HTTPStatus.OK

        coropool = [gen_ini_string() for _ in _ESTHER_EGGS]
        rets = await aio.gather(*coropool)
        assert rets.count(HTTPStatus.OK) == 1

    async def test_to_async(self) -> None:
        @to_async
        def read_ini_string(buffer: StringIO) -> dict[str, dict[str, str]]:
            ret: dict[str, dict[str, str]] = {}
            while (i := buffer.readline()):
                if not i:
                    break
                i = i.strip()
                if i.startswith('['):
                    left, right = i.index('['), i.index(']')
                    decl = i[left + 1:right]
                    ret[decl] = {}
                elif '=' in i:
                    key, val = i.split('=', 1)
                    ret[decl][key.strip()] = val.strip()
                else:
                    continue
            return ret

        dic = await read_ini_string(StringIO(TestAsyncUtils.NYA))
        assert len(dic) == 1

    async def test_cooldown(self) -> None:
        @cooldown(cd_callback=self.cd_callback, interval=3)
        async def sendmsg() -> int:
            print(f"I'm searching {choice(_ESTHER_EGGS)} in melobot group.")
            return HTTPStatus.OK

        pool = [sendmsg() for _ in range(5)]
        rets = await aio.gather(*pool)
        assert rets.count(HTTPStatus.TOO_MANY_REQUESTS) > 0

    async def test_semaphore(self) -> None:
        tickets = 10

        @semaphore(value=1)
        async def buyticket() -> int:
            nonlocal tickets
            if tickets <= 0:
                return HTTPStatus.EXPECTATION_FAILED
            tickets -= 1
            return HTTPStatus.OK

        pool = [buyticket() for _ in range(11)]
        rets = await aio.gather(*pool)
        assert not tickets and HTTPStatus.EXPECTATION_FAILED in rets

    async def test_timelimit(self) -> None:
        @timelimit(self.time_callback, timeout=5)
        async def foo() -> int:
            await aio.sleep(10)
            return HTTPStatus.OK

        ret = await foo()
        assert (await foo()) == HTTPStatus.REQUEST_TIMEOUT

    async def test_speedlimit(self) -> None:
        """In my opinion, just name it 'chancelimit'. """
        @speedlimit(self.lock_callback, limit=1, duration=5)
        async def foo() -> int:
            await aio.sleep(0)
            return HTTPStatus.OK

        pool = [foo() for _ in range(10)]
        rets = await aio.gather(*pool)
        assert rets.count(HTTPStatus.OK) <= 1


class TestCallableDispatch:
    timestamps: list[float] = []

    def foo(self) -> None:
        self.timestamps.append(aio.get_event_loop().time())

    async def afoo(self) -> None:
        await aio.sleep(0)
        self.timestamps.append(aio.get_event_loop().time())

    async def shut_task(
        self, task: aio.Task, delay: Optional[float] = None
    ) -> None:
        if delay is not None:
            await aio.sleep(delay)
        task.cancel()

    # mutable static member of a class may got affected
    #   both by object access (self.) and static access,
    # while hashable (like `str`) would be affected only by static access.

    # So to avoid messing up timestamps collection,
    # `self.timestamps.clear()` is set in the beginning of each test.

    async def test_call_later(self) -> None:
        self.timestamps.clear()
        a = call_later(self.foo, 5)
        begin = aio.get_event_loop().time()
        await aio.sleep(5)
        end = self.timestamps[0]
        assert isclose(end - begin, 5.01, abs_tol=0.01)

    # may not meaningful, just refer `test_call_later` is also OK.
    async def test_call_at(self) -> None:
        self.timestamps.clear()
        begin = aio.get_event_loop().time()
        a = call_at(self.foo, begin + 1)
        await aio.sleep(1)
        end = self.timestamps[0]
        assert end - begin < 0.1

    async def test_async_later(self) -> None:
        self.timestamps.clear()
        begin = aio.get_event_loop().time()
        await async_later(self.afoo(), 5)
        end = self.timestamps[0]
        assert isclose(end - begin, 5.01, abs_tol=0.01)

    # just refer `test_async_later`.
    async def test_async_at(self) -> None:
        self.timestamps.clear()
        begin = aio.get_event_loop().time()
        await async_at(self.afoo(), begin + 1)
        end = self.timestamps[0]
        assert end - begin < 0.1

    async def test_async_interval(self) -> None:
        self.timestamps.clear()
        t = async_interval(self.afoo, 1)
        await aio.gather(t, self.shut_task(t, 5))
        i = 1
        while i < len(self.timestamps):
            assert isclose(
                self.timestamps[i] - self.timestamps[i - 1],
                1.01,
                abs_tol=0.01
            )
            i += 1
        assert t.done()
