import asyncio as aio
import time
from contextlib import asynccontextmanager

from ..types.exceptions import *
from ..types.typing import *


class Singleton:
    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "__instance__"):
            cls.__instance__ = super(Singleton, cls).__new__(cls)
        return cls.__instance__


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

    def __init__(self, read_limit: int = None) -> None:
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
