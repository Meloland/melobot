import asyncio

from typing_extensions import TYPE_CHECKING, Any, AsyncGenerator, NotRequired, TypedDict, cast

from .reflect import logger

if TYPE_CHECKING:
    import socket

from .._run import set_loop_exc_handler
from ..typ import ExitCode, LogLevel


class LoopExcCtx(TypedDict):
    message: str
    exception: NotRequired[BaseException]
    future: NotRequired[asyncio.Future]
    task: NotRequired[asyncio.Task]
    handle: NotRequired[asyncio.Handle]
    protocol: NotRequired[asyncio.Protocol]
    transport: NotRequired[asyncio.Transport]
    socket: NotRequired["socket.socket"]
    asyncgen: NotRequired[AsyncGenerator]


_STRICT_LOOP_LOG = False


def set_loop_exc_log(strict: bool) -> None:
    global _STRICT_LOOP_LOG
    _STRICT_LOOP_LOG = strict


def _log_loop_exception(loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
    ctx = cast(LoopExcCtx, context)
    with_loop_ctx = {"loop": loop} | ctx
    exc = ctx.get("exception")
    msg = ctx["message"]

    if exc is not None:
        if (
            isinstance(exc, SystemExit)
            and exc.code is not None
            and int(exc.code) == ExitCode.RESTART.value
        ):
            logger.debug("收到重启信号，即将重启...")

        elif "exception was never retrieved" in msg:
            fut = ctx.get("future")
            task = ctx.get("task")
            if _STRICT_LOOP_LOG:
                try:
                    raise exc
                except BaseException:
                    logger.exception(f"从未捕获的异常的回溯栈：{msg}")
            logger.generic_obj(
                f"发现从未捕获的异常（这不一定是错误）：{msg}",
                {"future": fut, "task": task},
                level=LogLevel.ERROR if _STRICT_LOOP_LOG else LogLevel.DEBUG,
            )

        else:
            try:
                raise exc
            except BaseException:
                logger.exception(f"事件循环中抛出预期外的异常：{msg}")
                logger.generic_obj("相关变量信息：", with_loop_ctx, level=LogLevel.ERROR)

    else:
        logger.error(f"事件循环出现预期外的状况：{msg}")
        logger.generic_obj("相关变量信息：", with_loop_ctx, level=LogLevel.ERROR)


set_loop_exc_handler(_log_loop_exception)


def log_exc(exc: BaseException, msg: str, obj: Any = None) -> None:
    try:
        raise exc
    except BaseException:
        logger.exception(msg)
        if obj is not None:
            logger.generic_obj("相关变量信息：", obj, level=LogLevel.ERROR)
