import asyncio
from functools import partial
from logging import ERROR, WARNING, LogRecord, StreamHandler
from logging.handlers import RotatingFileHandler
from os import PathLike

from typing_extensions import TYPE_CHECKING, Any, Callable, cast

from .._lazy import singleton, singleton_clear
from .._render import get_rich_object, get_rich_repr
from .._run import (
    create_immunity_task,
    is_runner_running,
    register_closed_hook,
    register_started_hook,
)
from ..typ import P, T

if TYPE_CHECKING:
    from .base import LogInfo

_NO_LOG_OBJ_SIGN = object()


class FastStreamHandler(StreamHandler):
    def __init__(self, is_parellel: bool) -> None:
        super().__init__()
        self.render = RecordRender(is_parellel)

    def emit(self, record: LogRecord) -> None:
        if is_runner_running():
            t = create_immunity_task(self.render.async_format(record))
            t.add_done_callback(partial(_format_cb, record, super(FastStreamHandler, self).emit))
        else:
            self.render.sync_format(record)
            super().emit(record)


class FastRotatingFileHandler(RotatingFileHandler):
    def __init__(
        self,
        is_parellel: bool,
        filename: str | PathLike[str],
        mode: str = "a",
        maxBytes: int = 0,
        backupCount: int = 0,
        encoding: str | None = None,
        delay: bool = False,
        errors: str | None = None,
    ) -> None:
        super().__init__(filename, mode, maxBytes, backupCount, encoding, delay, errors)
        self.render = RecordRender(is_parellel)

    def emit(self, record: LogRecord) -> None:
        if is_runner_running():
            t = create_immunity_task(self.render.async_format(record))
            t.add_done_callback(
                partial(_format_cb, record, super(FastRotatingFileHandler, self).emit)
            )
        else:
            self.render.sync_format(record)
            super().emit(record)


@singleton
def get_exc_report_func() -> Callable[[BaseException, str], None]:
    from .report import log_exc

    return log_exc


def _format_cb(
    record: LogRecord, super_emit: Callable[[LogRecord], None], t: asyncio.Task[None]
) -> None:
    exc = t.exception()
    if exc is not None:
        get_exc_report_func()(exc, f"日志格式化渲染出现异常，内容：{record.msg}")
        return
    super_emit(record)


@singleton
class LogRenderRunner:
    def __init__(self) -> None:
        from .. import _render
        from ..mp import ProcessPoolExecutor  # noqa: F811

        self.pool = ProcessPoolExecutor(_render.__file__, max_workers=1)
        self.task_q = asyncio.Queue[tuple[Callable, asyncio.Future, Any, Any]]()
        self.ref_pairs: list[tuple[Any, str]] = []
        self.done = asyncio.Event()

        register_closed_hook(self._mark_done, allow_next=True)
        if is_runner_running():
            create_immunity_task(self._render_loop())
        else:
            register_started_hook(
                lambda: create_immunity_task(self._render_loop()),
                allow_next=True,
            )

    def add_ref(self, obj: Any, attr_name: str) -> None:
        self.ref_pairs.append((obj, attr_name))

    async def run(self, func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
        fut = asyncio.get_running_loop().create_future()
        await self.task_q.put((func, fut, args, kwargs))
        res = await fut
        return cast(T, res)

    def _mark_done(self) -> None:
        self.done.set()

    async def _render_loop(self) -> None:
        # 要尽可能将队列里所有日志都渲染完，而不是直接取消
        loop = asyncio.get_running_loop()
        done_task = create_immunity_task(self.done.wait())

        with self.pool:
            while True:
                # 想象一种情况：q_task 完成，随后日志渲染（发生了 await），回来时 done_task 已完成
                if done_task.done():
                    break
                q_task = create_immunity_task(self.task_q.get())
                await asyncio.wait((q_task, done_task), return_when=asyncio.FIRST_COMPLETED)
                if done_task.done():
                    if not q_task.done():
                        q_task.cancel()
                    else:
                        self.task_q.put_nowait(q_task.result())
                    break
                else:
                    func, fut, args, kwargs = q_task.result()
                    wrapped_func = partial(func, **kwargs)

                try:
                    res = await loop.run_in_executor(self.pool, wrapped_func, *args)
                except Exception as e:
                    fut.set_exception(e)
                else:
                    fut.set_result(res)

            # 收尾工作，此时把队列的任务消耗完即可
            # 也有可能此时再增加任务，但是至于能不能处理已经不重要
            # 因为至少 done_task 完成前的任务都处理了，这就足够了
            while self.task_q.qsize():
                func, fut, args, kwargs = self.task_q.get_nowait()
                wrapped_func = partial(func, **kwargs)
                try:
                    res = await loop.run_in_executor(self.pool, wrapped_func, *args)
                except Exception as e:
                    fut.set_exception(e)
                else:
                    fut.set_result(res)

        singleton_clear(self)
        new_runner = LogRenderRunner()
        for obj, attr_name in self.ref_pairs:
            try:
                setattr(obj, attr_name, new_runner)
                new_runner.add_ref(obj, attr_name)
            except Exception as e:
                get_exc_report_func()(e, f"清理 {self.__class__.__name__} 引用时发生异常")


class RecordRender:
    def __init__(self, is_parellel: bool = True) -> None:
        from rich.style import Style

        self.runner = LogRenderRunner() if is_parellel else None
        if self.runner is not None:
            self.runner.add_ref(self, "runner")

        self._yellow_style = Style(color="yellow")
        self._red_style = Style(color="red")

    def sync_format(self, record: LogRecord) -> None:
        log_info = cast("LogInfo", record.log_info)  # type: ignore[attr-defined]

        yellow_style = self._yellow_style
        red_style = self._red_style
        yellow_warn = log_info.yellow_warn
        red_error = log_info.red_error
        legacy = log_info.legacy
        msg = log_info.msg
        obj = log_info.obj

        if legacy:
            record.legacy_msg_str, record.colored_msg_str, record.msg_str = msg, "", msg

            if obj is _NO_LOG_OBJ_SIGN:
                record.legacy_obj, record.obj = "", ""
            else:
                record.legacy_obj = record.obj = get_rich_object(obj, no_color=True)[1]
            record.colored_obj = ""
            return

        record.legacy_msg_str = ""
        record.legacy_obj = ""

        if red_error and record.levelno >= ERROR:
            record.colored_msg_str, record.msg_str = get_rich_repr(msg, red_style)
        elif yellow_warn and ERROR > record.levelno >= WARNING:
            record.colored_msg_str, record.msg_str = get_rich_repr(msg, yellow_style)
        else:
            record.colored_msg_str, record.msg_str = get_rich_repr(msg)

        if obj is _NO_LOG_OBJ_SIGN:
            record.colored_obj, record.obj = "", ""
        elif red_error and record.levelno >= ERROR:
            record.legacy_obj = record.obj = get_rich_object(obj, no_color=True)[1]
            record.colored_obj = ""
        elif yellow_warn and ERROR > record.levelno >= WARNING:
            record.legacy_obj = record.obj = get_rich_object(obj, no_color=True)[1]
            record.colored_obj = ""
        else:
            record.colored_obj, record.obj = get_rich_object(obj)

    async def async_format(self, record: LogRecord) -> None:
        if self.runner is None:
            self.sync_format(record)
            return

        log_info = cast("LogInfo", record.log_info)  # type: ignore[attr-defined]

        yellow_style = self._yellow_style
        red_style = self._red_style
        yellow_warn = log_info.yellow_warn
        red_error = log_info.red_error
        legacy = log_info.legacy
        msg = log_info.msg
        obj = (
            self._to_easy_serialize(log_info.obj)
            if log_info.obj is not _NO_LOG_OBJ_SIGN
            else _NO_LOG_OBJ_SIGN
        )

        if legacy:
            record.legacy_msg_str, record.colored_msg_str, record.msg_str = msg, "", msg

            if obj is _NO_LOG_OBJ_SIGN:
                record.legacy_obj, record.obj = "", ""
            else:
                record.legacy_obj = record.obj = (
                    await self.runner.run(get_rich_object, obj, no_color=True)
                )[1]
            record.colored_obj = ""
            return

        record.legacy_msg_str = ""
        record.legacy_obj = ""

        if red_error and record.levelno >= ERROR:
            record.colored_msg_str, record.msg_str = await self.runner.run(
                get_rich_repr, msg, red_style
            )
        elif yellow_warn and ERROR > record.levelno >= WARNING:
            record.colored_msg_str, record.msg_str = await self.runner.run(
                get_rich_repr, msg, yellow_style
            )
        else:
            record.colored_msg_str, record.msg_str = await self.runner.run(get_rich_repr, msg)

        if obj is _NO_LOG_OBJ_SIGN:
            record.colored_obj, record.obj = "", ""
        elif red_error and record.levelno >= ERROR:
            record.legacy_obj = record.obj = (
                await self.runner.run(get_rich_object, obj, no_color=True)
            )[1]
            record.colored_obj = ""
        elif yellow_warn and ERROR > record.levelno >= WARNING:
            record.legacy_obj = record.obj = (
                await self.runner.run(get_rich_object, obj, no_color=True)
            )[1]
            record.colored_obj = ""
        else:
            record.colored_obj, record.obj = await self.runner.run(get_rich_object, obj)

    def _to_easy_serialize(self, obj: Any) -> Any:
        if isinstance(obj, str):
            return obj
        if isinstance(obj, (bytes, int, float, complex, bytearray)):
            return obj
        if obj in (None, True, False, Ellipsis, NotImplemented):
            return obj
        if isinstance(obj, (tuple, list, set)):
            return type(obj)(map(self._to_easy_serialize, obj))
        if isinstance(obj, dict):
            return {self._to_easy_serialize(k): self._to_easy_serialize(v) for k, v in obj.items()}
        return str(obj)
