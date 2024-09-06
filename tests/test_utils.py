# -*- encoding: utf-8 -*-
# @File   : test_utils.py
# @Time   : 2024/08/26 20:53:04
# @Author : Kariko Lin

from asyncio import sleep as sleep_async
from io import StringIO
from random import randint, choice
from time import sleep

from melobot.utils import *

from tests.base import *

# in case we may just need to test some async apis ...
# I just wrote pieces of junk. Nothing meaningful testing.

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
            print("Expected ValueError Triggered.")

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


class TestRWContext:
    SHARED_BUFFER = [''] * 10
    RW_CONTROL = RWContext(10)

    INTERVAL = 10

    async def write_randomized(self) -> None:
        async with self.RW_CONTROL.write():
            idx = randint(0, 9)
            if self.SHARED_BUFFER[idx]:
                return
            self.SHARED_BUFFER[idx] = choice([
                'qwqa', 'ElapsingDreams', 'frg2089',
                'Melorenae', 'aicorein', 'MelodyEcho',
                'SnowyKami', 'LiteeCiallo', '...'
            ])

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

