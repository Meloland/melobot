import asyncio
import base64
import time
from contextlib import asynccontextmanager
from datetime import datetime
from functools import wraps

from typing_extensions import Any, AsyncGenerator, Callable, Literal, cast

from ..typ.base import P, T


def get_obj_name(
    obj: Any,
    otype: Literal["callable", "class", "object"] | str = "object",
    default: str = "<anonymous %s>",
) -> str:
    """获取一个对象的限定名称或名称，这适用于一些类型较宽的参数。

    无法获取有效名称时，产生一个 `default % otype` 字符串

    例如某处接受一个 `Callable` 类型的参数，对于一般函数来说，使用
    `__qualname__` 或 `__name__` 可获得名称，但某些可调用对象这些值可能为 `None`
    或不存在。使用此方法可保证一定返回字符串

    .. code:: python

        def _(a: Callable) -> None:
            valid_str: str = get_obj_name(a, otype="callable")

        def _(a: type) -> None:
            valid_str: str = get_obj_name(a, otype="class")

        def _(a: Any) -> None:
            valid_str: str = get_obj_name(a, otype="type of a, only for str concat")


    :param obj: 对象
    :param otype: 预期的对象类型
    :param default: 无法获取任何有效名称时的默认字符串
    :return: 对象名称或默认字符串
    """
    if hasattr(obj, "__qualname__"):
        return cast(str, obj.__qualname__)

    if hasattr(obj, "__name__"):
        return cast(str, obj.__name__)

    return default % otype


def singleton(cls: Callable[P, T]) -> Callable[P, T]:
    """单例装饰器

    :param cls: 需要被单例化的可调用对象
    :return: 需要被单例化的可调用对象
    """
    obj_map = {}

    @wraps(cls)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        if cls not in obj_map:
            obj_map[cls] = cls(*args, **kwargs)
        return obj_map[cls]

    return wrapped


class RWContext:
    """异步读写上下文

    提供异步安全的读写上下文。在读取时可以多读，同时读写互斥。

    使用方法：

    .. code:: python

       rwc = RWContext()
       # 读时使用此控制器的安全读上下文：
       async with rwc.read():
           ...
       # 写时使用此控制器的安全写上下文：
       async with rwc.write():
           ...
    """

    def __init__(self, read_limit: int | None = None) -> None:
        """初始化异步读写上下文

        :param read_limit: 读取的数量限制，为空则不限制
        """
        self.write_semaphore = asyncio.Semaphore(1)
        self.read_semaphore = asyncio.Semaphore(read_limit) if read_limit else None
        self.read_num = 0
        self.read_num_lock = asyncio.Lock()

    @asynccontextmanager
    async def read(self) -> AsyncGenerator[None, None]:
        """上下文管理器，展开一个关于该对象的安全异步读上下文"""
        if self.read_semaphore:
            await self.read_semaphore.acquire()

        async with self.read_num_lock:
            if self.read_num == 0:
                await self.write_semaphore.acquire()
            self.read_num += 1

        try:
            yield
        finally:
            async with self.read_num_lock:
                self.read_num -= 1
                if self.read_num == 0:
                    self.write_semaphore.release()
                if self.read_semaphore:
                    self.read_semaphore.release()

    @asynccontextmanager
    async def write(self) -> AsyncGenerator[None, None]:
        """上下文管理器，展开一个关于该对象的安全异步写上下文"""
        await self.write_semaphore.acquire()
        try:
            yield
        finally:
            self.write_semaphore.release()


class SnowFlakeIdWorker:
    def __init__(self, datacenter_id: int, worker_id: int, sequence: int = 0) -> None:
        self.max_worker_id = -1 ^ (-1 << 3)
        self.max_datacenter_id = -1 ^ (-1 << 5)
        self.worker_id_shift = 12
        self.datacenter_id_shift = 12 + 3
        self.timestamp_left_shift = 12 + 3 + 5
        self.sequence_mask = -1 ^ (-1 << 12)
        self.startepoch = int(datetime(2022, 12, 11, 12, 8, 45).timestamp() * 1000)

        if worker_id > self.max_worker_id or worker_id < 0:
            raise ValueError("worker_id 值越界")
        if datacenter_id > self.max_datacenter_id or datacenter_id < 0:
            raise ValueError("datacenter_id 值越界")
        self.worker_id = worker_id
        self.datacenter_id = datacenter_id
        self.sequence = sequence
        self.last_timestamp = -1

    def _gen_timestamp(self) -> int:
        return int(time.time() * 1000)

    def get_id(self) -> int:
        timestamp = self._gen_timestamp()

        if timestamp < self.last_timestamp:
            raise ValueError(f"时钟回拨，{self.last_timestamp} 前拒绝 id 生成请求")
        if timestamp == self.last_timestamp:
            self.sequence = (self.sequence + 1) & self.sequence_mask
            if self.sequence == 0:
                timestamp = self._until_next_millis(self.last_timestamp)
        else:
            self.sequence = 0
        self.last_timestamp = timestamp
        new_id = (
            ((timestamp - self.startepoch) << self.timestamp_left_shift)
            | (self.datacenter_id << self.datacenter_id_shift)
            | (self.worker_id << self.worker_id_shift)
            | self.sequence
        )
        return new_id

    def get_b64_id(self, trim_pad: bool = True) -> str:
        id = base64.urlsafe_b64encode(
            self.get_id().to_bytes(8, byteorder="little")
        ).decode()
        if trim_pad:
            id = id.rstrip("=")
        return id

    def _until_next_millis(self, last_time: int) -> int:
        timestamp = self._gen_timestamp()
        while timestamp <= last_time:
            timestamp = self._gen_timestamp()
        return timestamp


_DEFAULT_ID_WORKER = SnowFlakeIdWorker(1, 1, 0)


def get_id() -> str:
    """从 melobot 内部 id 获取器获得一个 id 值，不保证线程安全。算法使用雪花算法

    :return: id 值
    """
    return _DEFAULT_ID_WORKER.get_b64_id()
