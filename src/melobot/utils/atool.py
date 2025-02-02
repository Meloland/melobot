import asyncio
import time

from typing_extensions import Any, Callable, Coroutine

from ..typ.base import T


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


def async_later(callback: Coroutine[Any, Any, T], delay: float) -> asyncio.Task[T]:
    """异步函数延迟调度（可自主选择是否等待）

    在指定的 `delay` 后调度一个 `callback` 执行。`callback` 是协程。

    返回一个 :class:`asyncio.Task` 对象，等待 :class:`asyncio.Task` 即是等待 `callback` 的返回值。

    :param callback: 协程（可有返回值）
    :param delay: 多长时间后调度
    :return: :class:`asyncio.Task` 对象
    """

    async def _later_task() -> T:
        try:
            await asyncio.sleep(delay)
            res = await callback
            return res
        except asyncio.CancelledError:
            callback.close()
            raise

    return asyncio.create_task(_later_task())


def async_at(callback: Coroutine[Any, Any, T], timestamp: float) -> asyncio.Task[T]:
    """异步函数指定时间调度（可自主选择是否等待）

    在指定的时间戳调度一个 `callback` 执行。`callback` 是协程。

    返回一个 :class:`asyncio.Task` 对象，等待 :class:`asyncio.Task` 即是等待 `callback` 的返回值。

    注意：如果 `callback` 未完成就被取消，需要捕获 :class:`asyncio.CancelledError`。

    :param callback: 协程（可有返回值）
    :param timestamp: 在什么时刻调度
    :return: :class:`asyncio.Task` 对象
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

    async def _interval_task() -> None:
        try:
            while True:
                coro = callback()
                await asyncio.sleep(interval)
                await coro
        except asyncio.CancelledError:
            coro.close()
            raise

    t = asyncio.create_task(_interval_task())
    return t
