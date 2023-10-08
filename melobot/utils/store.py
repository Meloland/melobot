import asyncio as aio
from contextlib import asynccontextmanager

from aiorwlock import RWLock

from ..interface.typing import *
from ..models.exceptions import *


class AsyncSafeObject:
    def __init__(self, val: Any=None) -> None:
        self.value = val
        self._lock = RWLock(fast=True)
        self.read_lock = self._lock.reader_lock
        self.write_lock = self._lock.writer_lock

    def get(self) -> Any:
        return self.value
    
    def set(self, val: Any) -> None:
        self.value = val


class BotStore:
    def __init__(self) -> None:
        self.__storage__: Dict[str, AsyncSafeObject] = {}
        self._lock = aio.Lock()

    def is_set(self, name: str) -> None:
        """
        判断值是否已经设置
        """
        obj = self.__storage__.get(name)
        return False if obj is None else True

    async def set(self, name: str, val: str) -> None:
        """
        安全地设置初值
        """
        async with self._lock:
            if not self.is_set(name):
                self.__storage__[name] = AsyncSafeObject(val)
            else:
                raise BotException("值已存在，使用 read_write 安全读写上下文修改值")

    @asynccontextmanager
    async def read(self, name: str) -> AsyncIterator[AsyncSafeObject]:
        """
        安全的读取上下文
        """
        if not self.is_set(name):
            raise BotException("值不存在，先通过 set 设置初值")
        
        obj = self.__storage__[name]
        async with obj.read_lock:
            yield obj
    
    @asynccontextmanager
    async def read_write(self, name: str) -> AsyncIterator[AsyncSafeObject]:
        """
        安全的读写上下文
        """
        if not self.is_set(name):
            raise BotException("值不存在，先通过 set 设置初值")
        
        obj = self.__storage__[name]
        async with obj.write_lock:
            yield obj


BOT_STORE = BotStore()
