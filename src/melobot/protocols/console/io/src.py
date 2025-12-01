from __future__ import annotations

import asyncio
import inspect

from prompt_toolkit import PromptSession, print_formatted_text
from prompt_toolkit.patch_stdout import patch_stdout
from typing_extensions import Any, ClassVar, cast

from melobot.io import AbstractIOSource
from melobot.log import LogLevel, logger

from ..const import PROTOCOL_IDENTIFIER
from .model import EchoPacket, InPacket, NormalOutputData, OutPacket, RawOutputData, StdinInputData


class ConsoleIO(AbstractIOSource[InPacket, OutPacket, EchoPacket]):
    __instance__: ClassVar[ConsoleIO | None] = None

    def __init__(
        self,
        record_in: bool = True,
        record_out: bool = False,
        **prompt_args: Any,
    ) -> None:
        super().__init__()
        self.protocol = PROTOCOL_IDENTIFIER
        if self.__instance__ is not None:
            raise ValueError(f"已经存在一个控制台源的实例: {self.__instance__}")

        self.prompt_args = prompt_args
        self.prompt_args.setdefault("message", "> ")
        self.prompt_args.setdefault("mouse_support", False)
        self.prompt_args.setdefault("show_frame", True)
        self.prompt_args.setdefault("set_exception_handler", False)
        self.prompt_args.setdefault("handle_sigint", False)

        self.record_in = record_in
        self.record_out = record_out
        self.prompt_session: PromptSession[str]

        self._prompt_args: dict[str, Any] = {}
        self._last_finished: asyncio.Future[None] | None = None
        self._lock = asyncio.Lock()
        self._opened = asyncio.Event()

    async def open(self) -> None:
        if self._opened.is_set():
            return

        async with self._lock:
            if self._opened.is_set():
                return

            self.prompt_session = PromptSession[str]()
            self._opened.set()
            logger.info("控制台源已开始运行")

    def opened(self) -> bool:
        return self._opened.is_set()

    async def close(self) -> None:
        if not self._opened.is_set():
            return

        async with self._lock:
            if not self._opened.is_set():
                return

            self._opened.clear()
            if self.prompt_session.app.is_running:
                self.prompt_session.app.exit()
            logger.info("控制台源已停止运行")

    def refresh_prompt_args(self) -> None:
        self._prompt_args = {}

    async def input(self) -> InPacket:
        await self._opened.wait()
        if self._last_finished is not None:
            await self._last_finished

        kwargs = self.prompt_args | self._prompt_args
        prompt = cast(str, kwargs.pop("message"))
        with patch_stdout():
            in_str = await self.prompt_session.prompt_async(prompt, **kwargs)  # type: ignore[arg-type]
        if self.record_in:
            logger.generic_lazy(
                "%s",
                lambda: f"控制台输入: {in_str}",
                level=LogLevel.DEBUG,
            )

        finish_fut = asyncio.get_running_loop().create_future()
        self._last_finished = finish_fut
        return InPacket(data=StdinInputData(content=in_str), finished=finish_fut)

    async def output(self, packet: OutPacket) -> EchoPacket:
        await self._opened.wait()
        data = packet.data

        if isinstance(data, RawOutputData):
            if self.record_out:
                logger.generic_lazy(
                    "%s",
                    lambda: f"控制台输出执行器: {data.executor}",
                    level=LogLevel.DEBUG,
                )
            ret = data.executor()
            if inspect.isawaitable(ret):
                await ret
        elif isinstance(data, NormalOutputData):
            out_str = data.content
            stream = data.stream
            if self.record_out:
                logger.generic_lazy(
                    "%s",
                    lambda: f"控制台输出: {out_str}，流：{stream}",
                    level=LogLevel.DEBUG,
                )
            print_formatted_text(out_str, file=stream)
        else:
            raise ValueError(f"暂不支持的输出包：{data}")

        _data = cast(NormalOutputData | RawOutputData, data)
        if _data.next_prompt_args is not None:
            self._prompt_args = _data.next_prompt_args
        return EchoPacket(noecho=True)
