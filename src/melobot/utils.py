import asyncio
import inspect
import time
import uuid
from contextlib import asynccontextmanager
from functools import wraps

from .exceptions import BotValidateError
from .types import Any, AsyncCallable, Callable, Coroutine, Optional, P, T, TypeVar, cast


def singleton(cls):
    instances = {}

    @wraps(cls)
    def wrapped():
        if cls not in instances:
            instances[cls] = cls()
        return instances[cls]

    return wrapped


class AsyncTwinEvent(asyncio.Event):
    """孪生 Event，会和绑定的一方时刻保持状态相反。"""

    def __init__(self) -> None:
        super().__init__()
        self._twin: Optional[AsyncTwinEvent] = None

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


def get_twin_event() -> tuple[asyncio.Event, asyncio.Event]:
    """获得两个时刻保持状态相反的 asyncio.Event。 获得的第一个为 unset，另一个为 set"""
    a, b = AsyncTwinEvent(), AsyncTwinEvent()
    a.bind(b)
    b.bind(a)
    return a, b


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

    def __init__(self, read_limit: Optional[int] = None) -> None:
        """初始化一个异步读写上下文

        :param read_limit: 读取的数量限制，为空则不限制
        """
        self.write_semaphore = asyncio.Semaphore(1)
        self.read_semaphore = asyncio.Semaphore(read_limit) if read_limit else None
        self.read_num = 0
        self.read_num_lock = asyncio.Lock()

    @asynccontextmanager
    async def read(self):
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
    async def write(self):
        await self.write_semaphore.acquire()
        try:
            yield
        finally:
            self.write_semaphore.release()


def get_id() -> str:
    """从 melobot 内部 id 获取器获得一个 id 值，不保证线程安全。

    :return: id 值
    """
    return uuid.uuid4().hex


def to_async(func: Callable[[], T]) -> Callable[[], Coroutine[Any, Any, T]]:
    """异步包装函数

    将一个同步函数包装为异步函数，保留返回值。如果需要传参使用 partial 包裹。

    :param func: 需要转换的函数
    :return: 异步函数
    """

    async def wrapper():
        return func()

    if callable(func):
        return wrapper
    else:
        raise BotValidateError("to_async 函数只支持同步函数作为参数")


def to_coro(obj: Callable[[], T] | asyncio.Future[T]) -> Coroutine[Any, Any, T]:
    """协程包装函数

    将一个同步函数或 Future 对象包装为协程，保留返回值。如果需要传参使用 partial 包裹。

    :param obj: 需要包装的同步函数或 Future 对象
    :return: 协程
    """

    async def as_coro(obj: asyncio.Future[T]) -> T:
        return await obj

    if isinstance(obj, asyncio.Future):
        return as_coro(obj)
    elif callable(obj):
        return to_async(obj)()
    else:
        raise BotValidateError("to_coro 函数只支持同步函数或 Future 对象作为参数")


CbRet_T = TypeVar("CbRet_T")
CbRet_T1 = TypeVar("CbRet_T1")
CbRet_T2 = TypeVar("CbRet_T2")
OriginRet_T = TypeVar("OriginRet_T")


def lock(callback: Optional[AsyncCallable[[], CbRet_T]] = None):
    """锁装饰器

    本方法作为异步函数的装饰器使用，可以为被装饰函数加锁。

    在获取锁冲突时，调用 `callback` 获得一个回调并执行。回调执行完毕后直接返回。

    `callback` 参数为空，只应用 :class:`asyncio.Lock` 的锁功能。

    被装饰函数的返回值：被装饰函数被执行 -> 被装饰函数返回值；执行任何回调 -> 那个回调的返回值

    :param callback: 获取锁冲突时的回调
    """
    alock = asyncio.Lock()

    def deco_func(
        func: AsyncCallable[P, OriginRet_T]
    ) -> AsyncCallable[P, CbRet_T | OriginRet_T]:

        @wraps(func)
        async def wrapped_func(
            *args: P.args, **kwargs: P.kwargs
        ) -> CbRet_T | OriginRet_T:
            if callback is not None and alock.locked():
                return await async_guard(callback)
            async with alock:
                return await async_guard(func, *args, **kwargs)

        return wrapped_func

    return deco_func


def cooldown(
    busy_callback: Optional[AsyncCallable[[], CbRet_T1]] = None,
    cd_callback: Optional[AsyncCallable[[float], CbRet_T2]] = None,
    interval: float = 5,
):
    """冷却装饰器

    本方法作为异步函数的装饰器使用，可以为被装饰函数添加 cd 时间。

    如果被装饰函数已有一个在运行，此时调用 `busy_callback` 生成回调并执行。回调执行完毕后直接返回。

    `busy_callback` 参数为空，则等待已运行的运行完成。随后执行下面的“冷却”处理逻辑。

    当被装饰函数没有在运行的，但冷却时间未结束：

       - `cd_callback` 不为空：使用 `cd_callback` 生成回调并执行。
       - `cd_callback` 为空，被装饰函数持续等待，直至冷却结束再执行。

    被装饰函数的返回值：被装饰函数被执行 -> 被装饰函数返回值；执行任何回调 -> 那个回调的返回值

    :param busy_callback: 已运行时的回调
    :param cd_callback: 冷却时间未结束的回调
    :param interval: 冷却时间
    """
    alock = asyncio.Lock()
    pre_finish_t = time.perf_counter() - interval - 1

    def deco_func(
        func: AsyncCallable[P, OriginRet_T]
    ) -> AsyncCallable[P, OriginRet_T | CbRet_T1 | CbRet_T2]:

        @wraps(func)
        async def wrapped_func(
            *args: P.args, **kwargs: P.kwargs
        ) -> OriginRet_T | CbRet_T1 | CbRet_T2:
            nonlocal pre_finish_t
            if busy_callback is not None and alock.locked():
                return await async_guard(busy_callback)

            async with alock:
                duration = time.perf_counter() - pre_finish_t
                if duration > interval:
                    ret = await async_guard(func, *args, **kwargs)
                    pre_finish_t = time.perf_counter()
                    return ret

                remain_t = interval - duration
                if cd_callback is not None:
                    return await async_guard(cd_callback, remain_t)
                else:
                    await asyncio.sleep(remain_t)
                    ret = await async_guard(func, *args, **kwargs)
                    pre_finish_t = time.perf_counter()
                    return ret

        return wrapped_func

    return deco_func


def semaphore(callback: Optional[AsyncCallable[[], CbRet_T]] = None, value: int = -1):
    """信号量装饰器

    本方法作为异步函数的装饰器使用，可以为被装饰函数添加信号量控制。

    在信号量无法立刻获取时，将调用 `callback` 获得回调并执行。回调执行完毕后直接返回。

    `callback` 参数为空，只应用 :class:`asyncio.Semaphore` 的信号量功能。

    被装饰函数的返回值：被装饰函数被执行 -> 被装饰函数返回值；执行任何回调 -> 那个回调的返回值

    :param callback: 信号量无法立即获取的回调
    :param value: 信号量阈值
    """
    a_semaphore = asyncio.Semaphore(value)

    def deco_func(
        func: AsyncCallable[P, OriginRet_T]
    ) -> AsyncCallable[P, OriginRet_T | CbRet_T]:

        @wraps(func)
        async def wrapped_func(
            *args: P.args, **kwargs: P.kwargs
        ) -> OriginRet_T | CbRet_T:
            if callback is not None and a_semaphore.locked():
                return await async_guard(callback)
            async with a_semaphore:
                return await async_guard(func, *args, **kwargs)

        return wrapped_func

    return deco_func


def timelimit(callback: Optional[AsyncCallable[[], CbRet_T]] = None, timeout: float = 5):
    """时间限制装饰器

    本方法作为异步函数的装饰器使用，可以为被装饰函数添加超时控制。

    超时之后，调用 `callback` 获得回调并执行，同时取消原任务。

    `callback` 参数为空，如果超时，则抛出 :class:`asyncio.TimeoutError` 异常。

    被装饰函数的返回值：被装饰函数被执行 -> 被装饰函数返回值；执行任何回调 -> 那个回调的返回值

    :param callback: 超时时的回调
    :param timeout: 超时时间
    """

    def deco_func(
        func: AsyncCallable[P, OriginRet_T]
    ) -> AsyncCallable[P, OriginRet_T | CbRet_T]:

        @wraps(func)
        async def wrapped_func(
            *args: P.args, **kwargs: P.kwargs
        ) -> OriginRet_T | CbRet_T:
            try:
                return await asyncio.wait_for(async_guard(func, *args, **kwargs), timeout)
            except asyncio.TimeoutError:
                if callback is None:
                    raise TimeoutError("timelimit 所装饰的任务已超时")
                return await async_guard(callback)

        return wrapped_func

    return deco_func


def speedlimit(
    callback: Optional[AsyncCallable[[], CbRet_T]] = None,
    limit: int = 60,
    duration: int = 60,
):
    """流量/速率限制装饰器

    本方法作为异步函数的装饰器使用，可以为被装饰函数添加流量控制：`duration` 秒内只允许 `limit` 次调用。

    超出调用速率限制后，调用 `callback` 获得回调并执行，同时取消原任务。

    `callback` 参数为空，等待直至满足速率控制要求再调用。

    被装饰函数的返回值：被装饰函数被执行 -> 被装饰函数返回值；执行任何回调 -> 那个回调的返回值。

    :param callback: 超出速率限制时的回调
    :param limit: `duration` 秒内允许调用多少次
    :param duration: 时长区间
    """
    called_num = 0
    min_start = time.perf_counter()
    if limit <= 0:
        raise BotValidateError("speedlimit 装饰器的 limit 参数必须 > 0")
    if duration <= 0:
        raise BotValidateError("speedlimit 装饰器的 duration 参数必须 > 0")

    def deco_func(
        func: AsyncCallable[P, OriginRet_T]
    ) -> AsyncCallable[P, OriginRet_T | CbRet_T]:

        @wraps(func)
        async def wrapped_func(
            *args: P.args, **kwargs: P.kwargs
        ) -> OriginRet_T | CbRet_T:
            fut = _wrapped_func(func, *args, **kwargs)
            fut = cast(asyncio.Future[CbRet_T | OriginRet_T | Exception], fut)
            fut_ret = await fut
            if isinstance(fut_ret, Exception):
                raise fut_ret
            else:
                return fut_ret

        return wrapped_func

    def _wrapped_func(
        func: AsyncCallable[P, T],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> asyncio.Future:
        # 分离出来定义，方便 result_set 调用形成递归。主要逻辑通过 Future 实现，有利于避免竞争问题。
        nonlocal called_num, min_start
        passed_time = time.perf_counter() - min_start
        res_fut: Any = asyncio.Future()

        if passed_time <= duration:
            if called_num < limit:
                called_num += 1
                asyncio.create_task(result_set(func, res_fut, -1, *args, **kwargs))

            elif callback is not None:
                asyncio.create_task(result_set(callback, res_fut, -1))

            else:
                asyncio.create_task(
                    result_set(func, res_fut, duration - passed_time, *args, **kwargs)
                )
        else:
            called_num, min_start = 0, time.perf_counter()
            called_num += 1
            asyncio.create_task(result_set(func, res_fut, -1, *args, **kwargs))

        return res_fut

    async def result_set(
        func: AsyncCallable[P, T],
        fut: asyncio.Future,
        delay: float,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        nonlocal called_num
        try:
            """
            只有依然在当前 duration 区间内，但超出调用次数限制的，需要等待。
            随后就是递归调用。delay > 0 为需要递归的分支。
            """
            if delay > 0:
                await asyncio.sleep(delay)
                res = await _wrapped_func(func, *args, **kwargs)
                fut.set_result(res)
                return

            res = await async_guard(func, *args, **kwargs)
            fut.set_result(res)

        except Exception as e:
            fut.set_result(e)

    return deco_func


def call_later(callback: Callable[[], None], delay: float):
    """同步函数延迟调度

    在指定的 `delay` 后调度一个 `callback` 执行。`callback` 应该是同步方法。

    :param callback: 同步函数
    :param delay: 多长时间后调度
    :return: :class:`asyncio.TimerHandle` 对象
    """
    return asyncio.get_running_loop().call_later(delay, callback)


def call_at(callback: Callable[[], None], timestamp: float):
    """同步函数指定时间调度

    在指定的时间戳调度一个 `callback` 执行。`callback` 应该是同步方法。`timestamp` <= 当前时刻回调立即执行

    :param callback: 同步函数
    :param timestamp: 在什么时刻调度
    :return: :class:`asyncio.TimerHandle` 对象
    """
    loop = asyncio.get_running_loop()
    if timestamp <= time.time_ns() / 1e9:
        return loop.call_soon(callback)
    else:
        return loop.call_later(timestamp - time.time_ns() / 1e9, callback)


def async_later(callback: Coroutine[Any, Any, T], delay: float) -> asyncio.Future[T]:
    """异步函数延迟调度（可自主选择是否等待）

    在指定的 `delay` 后调度一个 `callback` 执行。`callback` 是协程。

    返回一个 :class:`asyncio.Future` 对象，你可以选择等待或不等待。等待 :class:`asyncio.Future` 即是等待 `callback` 的返回值。

    注意：如果 `callback` 未完成就被取消，需要捕获 :class:`asyncio.CancelledError`。

    :param callback: 异步函数（可有返回值）
    :param delay: 多长时间后调度
    :return: :class:`asyncio.Future` 对象
    """

    async def async_cb(fut: asyncio.Future) -> None:
        try:
            await asyncio.sleep(delay)
            res = await callback
            fut.set_result(res)
        except asyncio.CancelledError:
            callback.close()

    fut: asyncio.Future[T] = asyncio.Future()
    asyncio.create_task(async_cb(fut))
    return fut


def async_at(callback: Coroutine[Any, Any, T], timestamp: float) -> asyncio.Future[T]:
    """异步函数指定时间调度（可自主选择是否等待）

    在指定的时间戳调度一个 `callback` 执行。`callback` 是协程。

    返回一个 :class:`asyncio.Future` 对象，你可以选择等待或不等待。等待 :class:`asyncio.Future` 即是等待 `callback` 的返回值。

    注意：如果 `callback` 未完成就被取消，需要捕获 :class:`asyncio.CancelledError`。

    :param callback: 异步函数（可有返回值）
    :param timestamp: 在什么时刻调度
    :return: :class:`asyncio.Future` 对象
    """
    if timestamp <= time.time_ns() / 1e9:
        return async_later(callback, 0)
    else:
        return async_later(callback, timestamp - time.time_ns() / 1e9)


def async_interval(
    callback: Callable[[], Coroutine[Any, Any, None]], interval: float
) -> asyncio.Task[None]:
    """异步函数间隔调度（类似 JavaScript 的 setInterval）

    每过时间间隔执行 `callback` 一次。`callback` 是返回协程的可调用对象（异步函数或 lambda 函数等）。

    返回一个 :class:`asyncio.Task` 对象，可使用该 task 取消调度过程。

    :param callback: 异步函数
    :param interval: 调度的间隔
    :return: :class:`asyncio.Task` 对象
    """

    async def interval_cb():
        try:
            while True:
                coro = callback()
                await asyncio.sleep(interval)
                await coro
        except asyncio.CancelledError:
            coro.close()

    t = asyncio.create_task(interval_cb())
    return t


async def async_guard(func: AsyncCallable[..., T], *args: Any, **kwargs: Any) -> T:
    """在使用异步可调用对象时，提供用户友好的验证"""
    if not callable(func):
        raise BotValidateError(
            f"{func} 不是异步可调用对象（返回 Awaitable 的可调用对象）"
        )

    await_obj = func(*args, **kwargs)
    if inspect.isawaitable(await_obj):
        return await await_obj
    raise BotValidateError(
        f"{func} 应该是异步函数，或其他异步可调用对象（返回 Awaitable 的可调用对象）。但它返回了：{await_obj}"
    )
