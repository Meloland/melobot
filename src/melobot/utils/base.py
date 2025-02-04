import asyncio
import inspect
from functools import wraps

from typing_extensions import Any, Awaitable, Callable, Coroutine

from ..exceptions import ValidateError
from ..typ.base import AsyncCallable, P, SyncOrAsyncCallable, T


def to_async(
    obj: SyncOrAsyncCallable[P, T] | Awaitable[T]
) -> Callable[P, Coroutine[Any, Any, T]]:
    """异步包装函数

    将一个可调用对象或可等待对象装饰为异步函数

    :param obj: 需要转换的可调用对象或可等待对象
    :return: 异步函数
    """
    if inspect.iscoroutinefunction(obj):
        return obj

    async def to_async_wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        if not inspect.isawaitable(obj):
            ret = obj(*args, **kwargs)
        else:
            ret = obj
        if inspect.isawaitable(ret):
            return await ret
        return ret

    if not inspect.isawaitable(obj):
        to_async_wrapped = wraps(obj)(to_async_wrapped)
    return to_async_wrapped


def to_coro(
    obj: SyncOrAsyncCallable[P, T] | Awaitable[T], *args: Any, **kwargs: Any
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
    return to_async(obj)(*args, **kwargs)  # type: ignore[arg-type]


async def async_guard(func: AsyncCallable[..., T], *args: Any, **kwargs: Any) -> T:
    """在使用异步可调用对象时，提供用户友好的验证"""
    if not callable(func):
        raise ValidateError(f"{func} 不是异步可调用对象（返回 Awaitable 的可调用对象）")

    await_obj = func(*args, **kwargs)
    if inspect.isawaitable(await_obj):
        return await await_obj
    raise ValidateError(
        f"{func} 应该是异步函数，或其他异步可调用对象（返回 Awaitable 的可调用对象）。但它返回了：{await_obj}，因此可能是同步函数"
    )


def to_sync(obj: SyncOrAsyncCallable[P, Any] | Awaitable[Any]) -> Callable[P, None]:
    """同步包装函数

    将一个可调用对象或可等待对象装饰为同步函数，但同步函数无法异步等待，包装后无法获取返回值

    因此仅用于接口兼容，如果提供了异步可调用对象，需要自行捕获内部可能的异常

    :param obj: 需要转换的可调用对象或可等待对象
    :return: 同步函数
    """

    def to_sync_wrapped(*args: P.args, **kwargs: P.kwargs) -> None:
        if inspect.isawaitable(obj):
            asyncio.create_task(to_coro(obj))
            return

        res = obj(*args, **kwargs)
        if inspect.isawaitable(res):
            asyncio.create_task(to_coro(res))

    if not inspect.isawaitable(obj):
        to_sync_wrapped = wraps(obj)(to_sync_wrapped)
    return to_sync_wrapped
