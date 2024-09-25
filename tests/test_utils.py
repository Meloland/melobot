# -*- encoding: utf-8 -*-
# @File   : test_utils.py
# @Time   : 2024/08/26 20:53:04
# @Author : Kariko Lin

from http import HTTPStatus
from io import StringIO
from random import randint, choice

from melobot.log import Logger, LogLevel
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


class TestMarkable:
    MARK = Markable()

    async def test_marking(self) -> None:
        self.MARK.flag_mark('ChlorideP', 'NyaAble', True)
        try:
            self.MARK.flag_mark("Meloland", 'aicorein', 2 ** randint(5, 11))
            self.MARK.flag_mark("Meloland", 'aicorein', 'kawaii dev desu.')
        except Exception as e:
            assert isinstance(e, ValueError)
            Logger().log(LogLevel.INFO, "Expected ValueError Triggered.")

    async def test_checkout(self) -> None:
        assert self.MARK.flag_check('ChlorideP', 'NyaAble', 1)


class TestAttrsReprable:
    class MelobotOfficialGroup(AttrsReprable):
        def __init__(self) -> None:
            # lazy to initialize other members.
            self.members = ['ChlorideP', ...]
            self.gid = 535705163
            self.cur_len = 32
            self.topics = ('bots', 'melobot', 'MelodyEcho')

    def test_repr(self) -> None:
        mbgroup = self.MelobotOfficialGroup()
        assert f'gid={mbgroup.gid}' in repr(mbgroup)


# Locatable seems doesn't need testing,
# since the object suffix validation may not clear.

# class TestLocatable:
#     pass


_ESTHER_EGGS = [
    'qwqa', 'ElapsingDreams', 'frg2089',
    'Melorenae', 'aicorein', 'MelodyEcho',
    'SnowyKami', 'LiteeCiallo', 'DislinkSforza'
]


class TestRWContext:
    SHARED_BUFFER = [''] * 10
    RW_CONTROL = RWContext(10)

    INTERVAL = 10

    async def write_randomized(self) -> None:
        esther_eggs = _ESTHER_EGGS.copy()
        esther_eggs.append('...')
        async with self.RW_CONTROL.write():
            idx = randint(0, 9)
            if self.SHARED_BUFFER[idx]:
                return
            self.SHARED_BUFFER[idx] = choice(esther_eggs)

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
        i = 0
        while i < self.INTERVAL:
            i += 1
            await self.write_randomized()
            _ = await self.read_raw()  # dropped.
            parsed = await self.read_parsed()
            assert parsed is None or len(
                [j for j in parsed if j.isupper()]) <= 1


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
        assert end - begin <= 5.01

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
        assert end - begin <= 5.01

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
            assert self.timestamps[i] - self.timestamps[i - 1] <= 1.01
            i += 1
        assert t.done()
