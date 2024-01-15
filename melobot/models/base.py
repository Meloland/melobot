import asyncio as aio
import sys
import time
import inspect
import pathlib
from contextlib import asynccontextmanager

from ..interface.exceptions import *
from ..interface.typing import *


class Singleton:
    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '__instance__'):
            cls.__instance__ = super(Singleton, cls).__new__(cls)
        return cls.__instance__


class IdWorker:
    """
    雪花算法生成 ID
    """
    def __init__(self, datacenter_id, worker_id, sequence=0) -> int:
        self.MAX_WORKER_ID = -1 ^ (-1 << 3)
        self.MAX_DATACENTER_ID = -1 ^ (-1 << 5)
        self.WOKER_ID_SHIFT = 12
        self.DATACENTER_ID_SHIFT = 12 + 3
        self.TIMESTAMP_LEFT_SHIFT = 12 + 3 + 5
        self.SEQUENCE_MASK = -1 ^ (-1 << 12)
        self.STARTEPOCH = 1064980800000
        # sanity check
        if worker_id > self.MAX_WORKER_ID or worker_id < 0:
            raise ValueError('worker_id 值越界')
        if datacenter_id > self.MAX_DATACENTER_ID or datacenter_id < 0:
            raise ValueError('datacenter_id 值越界')
        self.worker_id = worker_id
        self.datacenter_id = datacenter_id
        self.sequence = sequence
        self.last_timestamp = -1  # 上次计算的时间戳

    def __gen_timestamp(self) -> int:
        """
        生成整数时间戳
        """
        return int(time.time() * 1000)

    def get_id(self) -> int:
        """
        获取新 ID
        """
        timestamp = self.__gen_timestamp()

        # 时钟回拨
        if timestamp < self.last_timestamp:
            raise ValueError(f'时钟回拨，{self.last_timestamp} 前拒绝 id 生成请求')
        if timestamp == self.last_timestamp:
            self.sequence = (self.sequence + 1) & self.SEQUENCE_MASK
            if self.sequence == 0:
                timestamp = self.__til_next_millis(self.last_timestamp)
        else:
            self.sequence = 0
        self.last_timestamp = timestamp
        new_id = ((timestamp - self.STARTEPOCH) << self.TIMESTAMP_LEFT_SHIFT) | (self.datacenter_id << self.DATACENTER_ID_SHIFT) | (
                    self.worker_id << self.WOKER_ID_SHIFT) | self.sequence
        return new_id

    def __til_next_millis(self, last_timestamp) -> int:
        """
        等到下一毫秒
        """
        timestamp = self.__gen_timestamp()
        while timestamp <= last_timestamp:
            timestamp = self.__gen_timestamp()
        return timestamp


ID_WORKER = IdWorker(1, 1, 0)


class AsyncTwinEvent(aio.Event):
    """
    孪生 Event，会和绑定的一方时刻保持状态相反。
    """
    def __init__(self) -> None:
        super().__init__()
        self._twin: AsyncTwinEvent = None

    def bind(self, twin: "AsyncTwinEvent") -> None:
        self._twin = twin
        if self.is_set():
            super(AsyncTwinEvent, self._twin).clear()
        else:
            super(AsyncTwinEvent, self._twin).set()

    def set(self) -> None:
        super().set()
        if self._twin:
            super(AsyncTwinEvent, self._twin).clear()
    
    def clear(self) -> None:
        super().clear()
        if self._twin:
            super(AsyncTwinEvent, self._twin).set()


def get_twin_event() -> Tuple[aio.Event, aio.Event]:
    """
    获得两个时刻保持状态相反的 asyncio.Event。
    获得的第一个为 unset，另一个为 set
    """
    a, b = AsyncTwinEvent(), AsyncTwinEvent()
    a.bind(b)
    b.bind(a)
    return a, b


class RWController:
    """
    异步读写控制器。提供异步安全的读写上下文
    """
    def __init__(self, read_limit: int=None) -> None:
        @asynccontextmanager
        async def safe_read():
            nonlocal read_num, read_semaphore, write_semaphore, read_num_lock
            if read_semaphore:
                await read_semaphore.acquire()
            async with read_num_lock:
                if read_num == 0:
                    await write_semaphore.acquire()
                read_num += 1
            try:
                yield
            finally:
                async with read_num_lock:
                    read_num -= 1
                    if read_num == 0:
                        write_semaphore.release()
                    if read_semaphore:
                        read_semaphore.release()
        
        @asynccontextmanager
        async def safe_write():
            nonlocal write_semaphore
            await write_semaphore.acquire()
            try:
                yield
            finally:
                write_semaphore.release()
		
        write_semaphore = aio.Semaphore(1)
        if read_limit:
            read_semaphore = aio.Semaphore(read_limit)
        else:
            read_semaphore = None
        read_num = 0
        read_num_lock = aio.Lock()
        self.safe_read = safe_read
        self.safe_write = safe_write

def in_cwd(*path_str: str) -> str:
    """
    用于包内相对引用，解决内部相对路径不匹配的问题
    """
    fr = sys._getframe(1)
    call_file = fr.f_locals['__file__']
    return str(pathlib.Path(call_file).parent.joinpath(*path_str).resolve(strict=True))
