import asyncio
import inspect
import time
from functools import wraps

from typing_extensions import Any, AsyncContextManager, Callable, ContextManager, cast

from ..exceptions import UtilValidateError
from ..typ.base import AsyncCallable, P, SyncOrAsyncCallable, T, U, V
from .base import to_async


def if_(
    condition: SyncOrAsyncCallable[[], U] | U,
    reject: SyncOrAsyncCallable[[], None] | None = None,
    give_up: bool = True,
    accept: SyncOrAsyncCallable[[U], None] | None = None,
) -> Callable[[SyncOrAsyncCallable[P, T]], AsyncCallable[P, T | None]]:
    """条件判断装饰器

    :param condition: 用于判断的条件（如果是可调用对象，则先求值再转为 bool 值）
    :param reject: 当条件为 `False` 时，执行的回调
    :param give_up: 在条件为 `False` 时，是否放弃执行被装饰函数。当然，此选项不影响 `reject` 的执行
    :param accept: 当条件为 `True` 时，执行的回调
    """
    _condition = to_async(condition) if callable(condition) else condition
    _reject = to_async(reject) if reject is not None else reject
    _accept = to_async(accept) if accept is not None else accept

    def if_wrapper(func: SyncOrAsyncCallable[P, T]) -> AsyncCallable[P, T | None]:
        _func = to_async(func)

        @wraps(func)
        async def if_wrapped(*args: P.args, **kwargs: P.kwargs) -> T | None:
            if not callable(_condition):
                cond = _condition
            else:
                obj = _condition()
                cond = await obj if inspect.isawaitable(obj) else obj

            if not cond:
                if _reject is not None:
                    await _reject()
                if give_up:
                    return None
            else:
                if _accept is not None:
                    await _accept(cond)
            return await _func(*args, **kwargs)

        return if_wrapped

    return if_wrapper


def ctx(
    getter: SyncOrAsyncCallable[[], ContextManager | AsyncContextManager],
) -> Callable[[SyncOrAsyncCallable[P, T]], AsyncCallable[P, T]]:
    """上下文装饰器

    展开一个上下文，供被装饰函数使用。
    但注意此装饰器不支持获取上下文管理器 `yield` 的值

    :param getter: 上下文管理器或上下文管理器获取方法
    """

    _getter = to_async(getter)

    def ctx_wrapper(func: SyncOrAsyncCallable[P, T]) -> AsyncCallable[P, T]:
        _func = to_async(func)

        @wraps(func)
        async def ctx_wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                manager = await _getter()
            except Exception as e:
                raise UtilValidateError(
                    f"{ctx.__name__} 的 getter 参数为：{getter}，调用它获取上下文管理器失败：{e}"
                ) from e

            if isinstance(manager, ContextManager):
                with manager:
                    return await _func(*args, **kwargs)
            elif isinstance(manager, AsyncContextManager):
                async with manager:
                    return await _func(*args, **kwargs)
            else:
                raise UtilValidateError(
                    f"{ctx.__name__} 的 getter 参数为：{getter}，调用它返回了无效的上下文管理器"
                )

        return ctx_wrapped

    return ctx_wrapper


def lock(
    callback: SyncOrAsyncCallable[[], U] | None = None,
) -> Callable[[SyncOrAsyncCallable[P, T]], AsyncCallable[P, T | U]]:
    """锁装饰器

    本方法作为异步函数的装饰器使用，可以为被装饰函数加锁。

    在获取锁冲突时，调用 `callback` 获得一个回调并执行。回调执行完毕后直接返回。

    `callback` 参数为空，只应用 :class:`asyncio.Lock` 的锁功能。

    被装饰函数的返回值：被装饰函数被执行 -> 被装饰函数返回值；执行任何回调 -> 那个回调的返回值

    :param callback: 获取锁冲突时的回调
    """
    alock = asyncio.Lock()
    _callback = to_async(callback) if callback is not None else None

    def lock_wrapper(func: SyncOrAsyncCallable[P, T]) -> AsyncCallable[P, T | U]:
        _func = to_async(func)

        @wraps(func)
        async def lock_wrapped(*args: P.args, **kwargs: P.kwargs) -> T | U:
            if _callback is not None and alock.locked():
                return await _callback()
            async with alock:
                return await _func(*args, **kwargs)

        return lock_wrapped

    return lock_wrapper


def cooldown(
    busy_callback: SyncOrAsyncCallable[[], U] | None = None,
    cd_callback: SyncOrAsyncCallable[[float], V] | None = None,
    interval: float = 5,
) -> Callable[[SyncOrAsyncCallable[P, T]], AsyncCallable[P, T | U | V]]:
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

    _busy_callback = to_async(busy_callback) if busy_callback is not None else None
    _cd_callback = to_async(cd_callback) if cd_callback is not None else None

    def cooldown_wrapper(func: SyncOrAsyncCallable[P, T]) -> AsyncCallable[P, T | U | V]:
        _func = to_async(func)

        @wraps(func)
        async def cooldown_wrapped(*args: P.args, **kwargs: P.kwargs) -> T | U | V:
            nonlocal pre_finish_t
            if _busy_callback is not None and alock.locked():
                return await _busy_callback()

            async with alock:
                duration = time.perf_counter() - pre_finish_t
                if duration > interval:
                    ret = await _func(*args, **kwargs)
                    pre_finish_t = time.perf_counter()
                    return ret

                remain_t = interval - duration
                if _cd_callback is not None:
                    return await _cd_callback(remain_t)

                await asyncio.sleep(remain_t)
                ret = await _func(*args, **kwargs)
                pre_finish_t = time.perf_counter()
                return ret

        return cooldown_wrapped

    return cooldown_wrapper


def semaphore(
    callback: SyncOrAsyncCallable[[], U] | None = None, value: int = -1
) -> Callable[[SyncOrAsyncCallable[P, T]], AsyncCallable[P, T | U]]:
    """信号量装饰器

    本方法作为异步函数的装饰器使用，可以为被装饰函数添加信号量控制。

    在信号量无法立刻获取时，将调用 `callback` 获得回调并执行。回调执行完毕后直接返回。

    `callback` 参数为空，只应用 :class:`asyncio.Semaphore` 的信号量功能。

    被装饰函数的返回值：被装饰函数被执行 -> 被装饰函数返回值；执行任何回调 -> 那个回调的返回值

    :param callback: 信号量无法立即获取的回调
    :param value: 信号量阈值
    """
    a_semaphore = asyncio.Semaphore(value)
    _callback = to_async(callback) if callback is not None else None

    def semaphore_wrapper(func: SyncOrAsyncCallable[P, T]) -> AsyncCallable[P, T | U]:
        _func = to_async(func)

        @wraps(func)
        async def semaphore_wrapped(*args: P.args, **kwargs: P.kwargs) -> T | U:
            if _callback is not None and a_semaphore.locked():
                return await _callback()
            async with a_semaphore:
                return await _func(*args, **kwargs)

        return semaphore_wrapped

    return semaphore_wrapper


def timelimit(
    callback: SyncOrAsyncCallable[[], U] | None = None, timeout: float = 5
) -> Callable[[SyncOrAsyncCallable[P, T]], AsyncCallable[P, T | U]]:
    """时间限制装饰器

    本方法作为异步函数的装饰器使用，可以为被装饰函数添加超时控制。

    超时之后，调用 `callback` 获得回调并执行，同时取消原任务。

    `callback` 参数为空，如果超时，则抛出 :class:`asyncio.TimeoutError` 异常。

    被装饰函数的返回值：被装饰函数被执行 -> 被装饰函数返回值；执行任何回调 -> 那个回调的返回值

    :param callback: 超时时的回调
    :param timeout: 超时时间
    """
    _callback = to_async(callback) if callback is not None else None

    def timelimit_wrapper(func: SyncOrAsyncCallable[P, T]) -> AsyncCallable[P, T | U]:
        _func = to_async(func)

        @wraps(func)
        async def timelimit_wrapped(*args: P.args, **kwargs: P.kwargs) -> T | U:
            try:
                return await asyncio.wait_for(_func(*args, **kwargs), timeout)
            except asyncio.TimeoutError:
                if _callback is None:
                    raise TimeoutError(f"{timelimit.__name__} 所装饰的任务已超时") from None
                return await _callback()

        return timelimit_wrapped

    return timelimit_wrapper


def speedlimit(
    callback: SyncOrAsyncCallable[[], U] | None = None,
    limit: int = 60,
    duration: int = 60,
) -> Callable[[SyncOrAsyncCallable[P, T]], AsyncCallable[P, T | U]]:
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
        raise UtilValidateError("speedlimit 装饰器的 limit 参数必须 > 0")
    if duration <= 0:
        raise UtilValidateError("speedlimit 装饰器的 duration 参数必须 > 0")

    _callback = to_async(callback) if callback is not None else None

    def speedlimit_wrapper(func: SyncOrAsyncCallable[P, T]) -> AsyncCallable[P, T | U]:
        _func = to_async(func)

        @wraps(func)
        async def speedlimit_wrapped(*args: P.args, **kwargs: P.kwargs) -> T | U:
            fut = _speedlimit_wrapped(_func, *args, **kwargs)
            fut = cast(asyncio.Future[T | U | Exception], fut)
            fut_ret = await fut
            if isinstance(fut_ret, Exception):
                raise fut_ret
            return fut_ret

        return speedlimit_wrapped

    def _speedlimit_wrapped(
        func: AsyncCallable[P, T],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> asyncio.Future:
        # 分离出来定义，方便 result_set 调用形成递归。主要逻辑通过 Future 实现，有利于避免竞争问题。
        nonlocal called_num, min_start
        passed_time = time.perf_counter() - min_start
        res_fut: Any = asyncio.get_running_loop().create_future()

        if passed_time <= duration:
            if called_num < limit:
                called_num += 1
                asyncio.create_task(_speedlimit_set_result(func, res_fut, -1, *args, **kwargs))

            elif _callback is not None:
                asyncio.create_task(_speedlimit_set_result(_callback, res_fut, -1))

            else:
                asyncio.create_task(
                    _speedlimit_set_result(func, res_fut, duration - passed_time, *args, **kwargs)
                )
        else:
            called_num, min_start = 0, time.perf_counter()
            called_num += 1
            asyncio.create_task(_speedlimit_set_result(func, res_fut, -1, *args, **kwargs))

        return cast(asyncio.Future, res_fut)

    async def _speedlimit_set_result(
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
        try:
            if delay > 0:
                await asyncio.sleep(delay)
                res = await _speedlimit_wrapped(func, *args, **kwargs)
                fut.set_result(res)
                return

            res = await func(*args, **kwargs)
            fut.set_result(res)

        except Exception as e:
            fut.set_result(e)

    return speedlimit_wrapper
