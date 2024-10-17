import asyncio
import base64
import inspect
import time
from contextlib import asynccontextmanager
from datetime import datetime
from functools import wraps
from typing import Any, AsyncGenerator, Awaitable, Callable, Coroutine, TypeVar, cast

from typing_extensions import Self

from .exceptions import ValidateError
from .typ import AsyncCallable, P, T


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


class Markable:
    """可标记对象

    无需直接实例化，而是用作接口在其他类中继承
    """

    def __init__(self) -> None:
        self._flags: dict[str, dict[str, Any]] = {}

    def flag_mark(self, namespace: str, flag_name: str, val: Any = None) -> None:
        """在 `namespace` 命名空间中设置 `flag_name` 标记，值为 `val`

        注：不同的对象并不共享 `namespace`，`namespace` 只适用于单个对象

        :param namespace: 命名空间
        :param flag_name: 标记名
        :param val: 标记值
        """
        self._flags.setdefault(namespace, {})

        if flag_name in self._flags[namespace].keys():
            raise ValueError(
                f"标记失败。对象的命名空间 {namespace} 中已存在名为 {flag_name} 的标记"
            )

        self._flags[namespace][flag_name] = val

    def flag_check(self, namespace: str, flag_name: str, val: Any = None) -> bool:
        """检查 `namespace` 命名空间中 `flag_name` 标记值是否为 `val`

        注：不同的对象并不共享 `namespace`，`namespace` 只适用于单个对象

        :param namespace: 命名空间
        :param flag_name: 标记名
        :param val: 标记值
        :return: 是否通过检查
        """
        if self._flags.get(namespace) is None:
            return False
        if flag_name not in self._flags[namespace].keys():
            return False
        flag = self._flags[namespace][flag_name]

        if val is None:
            return flag is None
        return cast(bool, flag == val)


class AttrsReprable:
    def __repr__(self) -> str:
        attrs = ", ".join(
            f"{k}={repr(v)}" for k, v in self.__dict__.items() if not k.startswith("_")
        )
        return f"{self.__class__.__name__}({attrs})"


class Locatable:
    def __new__(cls, *_args: Any, **_kwargs: Any) -> Self:
        obj = super().__new__(cls)
        obj.__obj_location__ = obj._init_location()  # type: ignore[attr-defined]
        return obj

    def __init__(self) -> None:
        self.__obj_location__: tuple[str, str, int]

    @staticmethod
    def _init_location() -> tuple[str, str, int]:
        frame = inspect.currentframe()
        while frame:
            if frame.f_code.co_name == "<module>":
                return (
                    frame.f_globals["__name__"],
                    frame.f_globals["__file__"],
                    frame.f_lineno,
                )
            frame = frame.f_back

        return (
            "<unknown module>",
            "<unknown file>",
            -1,
        )

    @property
    def __obj_module__(self) -> str:
        return self.__obj_location__[0]

    @property
    def __obj_file__(self) -> str:
        return self.__obj_location__[1]

    @property
    def __obj_line__(self) -> int:
        return self.__obj_location__[2]


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


def to_async(
    obj: Callable[P, T] | AsyncCallable[P, T] | Awaitable[T]
) -> Callable[P, Coroutine[Any, Any, T]]:
    """异步包装函数

    将一个可调用对象或可等待对象装饰为异步函数

    :param obj: 需要转换的可调用对象或可等待对象
    :return: 异步函数
    """
    if inspect.iscoroutinefunction(obj):
        return obj

    async def async_wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        if not inspect.isawaitable(obj):
            ret = obj(*args, **kwargs)
        else:
            ret = obj
        if inspect.isawaitable(ret):
            return await ret
        return ret

    if not inspect.isawaitable(obj):
        async_wrapped = wraps(obj)(async_wrapped)
    return async_wrapped


def to_coro(
    obj: Callable[P, T] | AsyncCallable[P, T] | Awaitable[T],
    *args: Any,
    **kwargs: Any,
) -> Coroutine[Any, Any, T]:
    """协程包装函数

    将一个可调用对象或可等待对象装饰为异步函数，并返回对应的协程

    :param obj: 需要包装的可调用对象或可等待对象
    :param args: 需要使用的位置参数
    :param kwargs: 需要使用的关键字参数
    :return: 协程
    """
    if inspect.iscoroutine(obj):
        return obj
    return to_async(obj)(*args, **kwargs)


CbRetT = TypeVar("CbRetT")
FirstCbRetT = TypeVar("FirstCbRetT")
SecondCbRetT = TypeVar("SecondCbRetT")
OriginRetT = TypeVar("OriginRetT")


def lock(
    callback: AsyncCallable[[], CbRetT] | None = None
) -> Callable[[AsyncCallable[P, OriginRetT]], AsyncCallable[P, CbRetT | OriginRetT]]:
    """锁装饰器

    本方法作为异步函数的装饰器使用，可以为被装饰函数加锁。

    在获取锁冲突时，调用 `callback` 获得一个回调并执行。回调执行完毕后直接返回。

    `callback` 参数为空，只应用 :class:`asyncio.Lock` 的锁功能。

    被装饰函数的返回值：被装饰函数被执行 -> 被装饰函数返回值；执行任何回调 -> 那个回调的返回值

    :param callback: 获取锁冲突时的回调
    """
    alock = asyncio.Lock()

    def deco_func(
        func: AsyncCallable[P, OriginRetT]
    ) -> AsyncCallable[P, CbRetT | OriginRetT]:

        @wraps(func)
        async def wrapped_func(*args: P.args, **kwargs: P.kwargs) -> CbRetT | OriginRetT:
            if callback is not None and alock.locked():
                return await async_guard(callback)
            async with alock:
                return await async_guard(func, *args, **kwargs)

        return wrapped_func

    return deco_func


def cooldown(
    busy_callback: AsyncCallable[[], FirstCbRetT] | None = None,
    cd_callback: AsyncCallable[[float], SecondCbRetT] | None = None,
    interval: float = 5,
) -> Callable[
    [AsyncCallable[P, OriginRetT]],
    AsyncCallable[P, OriginRetT | FirstCbRetT | SecondCbRetT],
]:
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
        func: AsyncCallable[P, OriginRetT]
    ) -> AsyncCallable[P, OriginRetT | FirstCbRetT | SecondCbRetT]:

        @wraps(func)
        async def wrapped_func(
            *args: P.args, **kwargs: P.kwargs
        ) -> OriginRetT | FirstCbRetT | SecondCbRetT:
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

                await asyncio.sleep(remain_t)
                ret = await async_guard(func, *args, **kwargs)
                pre_finish_t = time.perf_counter()
                return ret

        return wrapped_func

    return deco_func


def semaphore(
    callback: AsyncCallable[[], CbRetT] | None = None, value: int = -1
) -> Callable[[AsyncCallable[P, OriginRetT]], AsyncCallable[P, OriginRetT | CbRetT]]:
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
        func: AsyncCallable[P, OriginRetT]
    ) -> AsyncCallable[P, OriginRetT | CbRetT]:

        @wraps(func)
        async def wrapped_func(*args: P.args, **kwargs: P.kwargs) -> OriginRetT | CbRetT:
            if callback is not None and a_semaphore.locked():
                return await async_guard(callback)
            async with a_semaphore:
                return await async_guard(func, *args, **kwargs)

        return wrapped_func

    return deco_func


def timelimit(
    callback: AsyncCallable[[], CbRetT] | None = None, timeout: float = 5
) -> Callable[[AsyncCallable[P, OriginRetT]], AsyncCallable[P, OriginRetT | CbRetT]]:
    """时间限制装饰器

    本方法作为异步函数的装饰器使用，可以为被装饰函数添加超时控制。

    超时之后，调用 `callback` 获得回调并执行，同时取消原任务。

    `callback` 参数为空，如果超时，则抛出 :class:`asyncio.TimeoutError` 异常。

    被装饰函数的返回值：被装饰函数被执行 -> 被装饰函数返回值；执行任何回调 -> 那个回调的返回值

    :param callback: 超时时的回调
    :param timeout: 超时时间
    """

    def deco_func(
        func: AsyncCallable[P, OriginRetT]
    ) -> AsyncCallable[P, OriginRetT | CbRetT]:

        @wraps(func)
        async def wrapped_func(*args: P.args, **kwargs: P.kwargs) -> OriginRetT | CbRetT:
            try:
                return await asyncio.wait_for(async_guard(func, *args, **kwargs), timeout)
            except asyncio.TimeoutError:
                if callback is None:
                    raise TimeoutError("timelimit 所装饰的任务已超时") from None
                return await async_guard(callback)

        return wrapped_func

    return deco_func


def speedlimit(
    callback: AsyncCallable[[], CbRetT] | None = None,
    limit: int = 60,
    duration: int = 60,
) -> Callable[[AsyncCallable[P, OriginRetT]], AsyncCallable[P, OriginRetT | CbRetT]]:
    """流量/速率限制装饰器（使用固定窗口算法）

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
        raise ValidateError("speedlimit 装饰器的 limit 参数必须 > 0")
    if duration <= 0:
        raise ValidateError("speedlimit 装饰器的 duration 参数必须 > 0")

    def deco_func(
        func: AsyncCallable[P, OriginRetT]
    ) -> AsyncCallable[P, OriginRetT | CbRetT]:

        @wraps(func)
        async def wrapped_func(*args: P.args, **kwargs: P.kwargs) -> OriginRetT | CbRetT:
            fut = _wrapped_func(func, *args, **kwargs)
            fut = cast(asyncio.Future[CbRetT | OriginRetT | Exception], fut)
            fut_ret = await fut
            if isinstance(fut_ret, Exception):
                raise fut_ret
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

        return cast(asyncio.Future, res_fut)

    async def result_set(
        func: AsyncCallable[P, T],
        fut: asyncio.Future,
        delay: float,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        """
        只有依然在当前 duration 区间内，但超出调用次数限制的，需要等待。
        随后就是递归调用。delay > 0 为需要递归的分支。
        """
        nonlocal called_num
        try:
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


def call_later(callback: Callable[[], None], delay: float) -> asyncio.TimerHandle:
    """同步函数延迟调度

    在指定的 `delay` 后调度一个 `callback` 执行。`callback` 应该是同步方法。

    :param callback: 同步函数
    :param delay: 多长时间后调度
    :return: :class:`asyncio.TimerHandle` 对象
    """
    return asyncio.get_running_loop().call_later(delay, callback)


def call_at(callback: Callable[[], None], timestamp: float) -> asyncio.TimerHandle:
    """同步函数指定时间调度

    在指定的时间戳调度一个 `callback` 执行。`callback` 应该是同步方法。`timestamp` <= 当前时刻回调立即执行

    :param callback: 同步函数
    :param timestamp: 在什么时刻调度
    :return: :class:`asyncio.TimerHandle` 对象
    """
    loop = asyncio.get_running_loop()
    if timestamp <= time.time_ns() / 1e9:
        return loop.call_later(0, callback)

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

    async def interval_cb() -> None:
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
        raise ValidateError(f"{func} 不是异步可调用对象（返回 Awaitable 的可调用对象）")

    await_obj = func(*args, **kwargs)
    if inspect.isawaitable(await_obj):
        return await await_obj
    raise ValidateError(
        f"{func} 应该是异步函数，或其他异步可调用对象（返回 Awaitable 的可调用对象）。但它返回了：{await_obj}"
    )
