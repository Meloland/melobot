import asyncio as aio
import pathlib
import re
import sys
import time
from asyncio import iscoroutine
from functools import wraps

from ..types.exceptions import *
from ..types.typing import *


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


def clear_cq(s: str) -> str:
    """
    去除文本中的所有 CQ 字符串
    """
    regex = re.compile(r"\[CQ:.*?\]")
    return regex.sub("", s)


def lock(cb_maker: Callable[[None], Coroutine[Any, Any, Any]]) -> Callable:
    """
    锁装饰器，可以为被装饰的异步函数/方法加锁。
    同时在获取锁冲突时，调用 cb_maker 获得一个回调并执行。
    """
    alock = aio.Lock()
    if not callable(cb_maker):
        raise BotValueError(
            f"lock 装饰器的 cb_maker 参数不可调用，cb_maker 值为：{cb_maker}"
        )

    def deco_func(func: Callable) -> Callable:
        @wraps(func)
        async def wrapped_func(*args, **kwargs):
            if alock.locked():
                cb = cb_maker()
                if not iscoroutine(cb):
                    raise BotValueError(
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

    如果被装饰方法没有正在运行的，但在冷却完成前被调用，且此时 cd_cb_maker 不为 None，
    会使用 cd_cb_maker 生成一个回调并执行。如果此时 cd_cb_maker 为 None，
    被装饰方法会等待冷却结束再执行
    """
    alock = aio.Lock()
    pre_finish_t = time.time() - interval - 1
    if not callable(busy_cb_maker):
        raise BotValueError(
            f"cooldown 装饰器的 busy_cb_maker 参数不可调用，busy_cb_maker 值为：{busy_cb_maker}"
        )
    if cd_cb_maker is not None and not callable(cd_cb_maker):
        raise BotValueError(
            f"cooldown 装饰器的 cd_cb_maker 参数不可调用，cd_cb_maker 值为：{cd_cb_maker}"
        )

    def deco_func(func: Callable) -> Callable:
        @wraps(func)
        async def wrapped_func(*args, **kwargs):
            nonlocal pre_finish_t
            if alock.locked():
                busy_cb = busy_cb_maker()
                if not iscoroutine(busy_cb):
                    raise BotValueError(
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
                        raise BotValueError(
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
    同时在信号量无法立刻获取时，调用 cb_maker 获得回调并执行。
    """
    a_semaphore = aio.Semaphore(value)
    if not callable(cb_maker):
        raise BotValueError(
            f"semaphore 装饰器的 cb_maker 参数不可调用，cb_maker 值为：{cb_maker}"
        )

    def deco_func(func: Callable) -> Callable:
        @wraps(func)
        async def wrapped_func(*args, **kwargs):
            if a_semaphore.locked():
                cb = cb_maker()
                if not iscoroutine(cb):
                    raise BotValueError(
                        f"semaphore 装饰器的 cb_maker 返回的不是协程，返回的回调为：{cb}"
                    )
                return await cb
            async with a_semaphore:
                return await func(*args, **kwargs)

        return wrapped_func

    return deco_func
