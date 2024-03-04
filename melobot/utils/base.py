import asyncio as aio
import pathlib
import re
import sys
import time
from asyncio import iscoroutine
from functools import wraps

from ..types.exceptions import *
from ..types.typing import *


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
            raise ValueError("worker_id 值越界")
        if datacenter_id > self.MAX_DATACENTER_ID or datacenter_id < 0:
            raise ValueError("datacenter_id 值越界")
        self.worker_id = worker_id
        self.datacenter_id = datacenter_id
        self.sequence = sequence
        self.last_timestamp = -1

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
            raise ValueError(f"时钟回拨，{self.last_timestamp} 前拒绝 id 生成请求")
        if timestamp == self.last_timestamp:
            self.sequence = (self.sequence + 1) & self.SEQUENCE_MASK
            if self.sequence == 0:
                timestamp = self.__til_next_millis(self.last_timestamp)
        else:
            self.sequence = 0
        self.last_timestamp = timestamp
        new_id = (
            ((timestamp - self.STARTEPOCH) << self.TIMESTAMP_LEFT_SHIFT)
            | (self.datacenter_id << self.DATACENTER_ID_SHIFT)
            | (self.worker_id << self.WOKER_ID_SHIFT)
            | self.sequence
        )
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


def get_id() -> int:
    """
    获取一个全局唯一 id，由 melobot 内部 id 生成器提供
    """
    return ID_WORKER.get_id()


def this_dir(*relative_path: str) -> str:
    """
    包内脚本可通过该方法获取所在目录的绝对路径。提供 relative_path 参数，
    可自动拼接绝对路径。

    建议只在 py 脚本的顶级作用域调用，不要在其他作用域中调用
    """
    fr = sys._getframe(1)
    call_file = fr.f_locals["__file__"]
    return str(
        pathlib.Path(call_file).parent.joinpath(*relative_path).resolve(strict=True)
    )


def get_cq_text(s: str) -> str:
    """
    从 cq 消息字符串中，获取纯净的 cq text 类型消息
    """
    regex = re.compile(r"\[CQ:.*?\]")
    return regex.sub("", s)


def to_async(func: Callable):
    """
    异步包装器，将一个同步函数包装为异步函数。保留返回值。
    如果需要传参使用 partial 包裹
    """

    async def wrapper():
        return func()

    return wrapper


def to_coro(func: Callable):
    """
    协程包装器，将一个同步函数包装为协程。保留返回值。
    如果需要传参使用 partial 包裹
    """

    f = to_async(func)
    return f()


def lock(cb_maker: Callable[[None], Coroutine[Any, Any, Any]]) -> Callable:
    """
    锁装饰器，可以为被装饰的异步函数/方法加锁。
    在获取锁冲突时，调用 cb_maker 获得一个回调并执行。回调执行完毕后直接返回
    """
    alock = aio.Lock()
    if not callable(cb_maker):
        raise BotBaseUtilsError(
            f"lock 装饰器的 cb_maker 参数不可调用，cb_maker 值为：{cb_maker}"
        )

    def deco_func(func: Callable) -> Callable:
        @wraps(func)
        async def wrapped_func(*args, **kwargs):
            if alock.locked():
                cb = cb_maker()
                if not iscoroutine(cb):
                    raise BotBaseUtilsError(
                        f"lock 装饰器的 cb_maker 返回的不是协程，返回的回调为：{cb}"
                    )
                return await cb
            async with alock:
                return await func(*args, **kwargs)

        return wrapped_func

    return deco_func


def cooldown(
    busy_cb_maker: Callable[[None], Coroutine[Any, Any, Any]],
    cd_cb_maker: Callable[[float], Coroutine[Any, Any, Any]] = None,
    interval: float = 5,
) -> Callable:
    """
    冷却装饰器，可以为被装饰的异步函数/方法添加 cd 时间。
    cd_cb_maker 的类型：接受一个 float 参数（cd 剩余时间），
    返回一个协程的 Callable 对象。

    如果被装饰方法已有一个在运行，此时会直接调用 busy_cb_maker 生成一个回调并执行。
    回调执行完毕后直接返回。

    如果被装饰方法没有正在运行的，但在冷却完成前被调用，且此时 cd_cb_maker 不为 None，
    会使用 cd_cb_maker 生成一个回调并执行。如果此时 cd_cb_maker 为 None，
    被装饰方法会持续等待直至冷却结束再执行
    """
    alock = aio.Lock()
    pre_finish_t = time.time() - interval - 1
    if not callable(busy_cb_maker):
        raise BotBaseUtilsError(
            f"cooldown 装饰器的 busy_cb_maker 参数不可调用，busy_cb_maker 值为：{busy_cb_maker}"
        )
    if cd_cb_maker is not None and not callable(cd_cb_maker):
        raise BotBaseUtilsError(
            f"cooldown 装饰器的 cd_cb_maker 参数不可调用，cd_cb_maker 值为：{cd_cb_maker}"
        )

    def deco_func(func: Callable) -> Callable:
        @wraps(func)
        async def wrapped_func(*args, **kwargs):
            nonlocal pre_finish_t
            if alock.locked():
                busy_cb = busy_cb_maker()
                if not iscoroutine(busy_cb):
                    raise BotBaseUtilsError(
                        f"cooldown 装饰器的 busy_cb_maker 返回的不是协程，返回的回调为：{busy_cb}"
                    )
                return await busy_cb

            async with alock:
                duration = time.time() - pre_finish_t
                if duration > interval:
                    ret = await func(*args, **kwargs)
                    pre_finish_t = time.time()
                    return ret

                remain_t = interval - duration
                if cd_cb_maker is not None:
                    cd_cb = cd_cb_maker(remain_t)
                    if not iscoroutine(cd_cb):
                        raise BotBaseUtilsError(
                            f"cooldown 装饰器的 cd_cb_maker 返回的不是协程，返回的回调为：{cd_cb}"
                        )
                    return await cd_cb
                else:
                    await aio.sleep(remain_t)
                    ret = await func(*args, **kwargs)
                    pre_finish_t = time.time()
                    return ret

        return wrapped_func

    return deco_func


def semaphore(
    cb_maker: Callable[[None], Coroutine[Any, Any, Any]], value: int = -1
) -> Callable:
    """
    信号量装饰器，可以为被装饰的异步函数/方法添加信号量控制。
    在信号量无法立刻获取时，将调用 cb_maker 获得回调并执行。回调执行完毕后直接返回
    """
    a_semaphore = aio.Semaphore(value)
    if not callable(cb_maker):
        raise BotBaseUtilsError(
            f"semaphore 装饰器的 cb_maker 参数不可调用，cb_maker 值为：{cb_maker}"
        )

    def deco_func(func: Callable) -> Callable:
        @wraps(func)
        async def wrapped_func(*args, **kwargs):
            if a_semaphore.locked():
                cb = cb_maker()
                if not iscoroutine(cb):
                    raise BotBaseUtilsError(
                        f"semaphore 装饰器的 cb_maker 返回的不是协程，返回的回调为：{cb}"
                    )
                return await cb
            async with a_semaphore:
                return await func(*args, **kwargs)

        return wrapped_func

    return deco_func
