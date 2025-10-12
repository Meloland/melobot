from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum

from typing_extensions import Any, Literal, TypeVar

from melobot.io import EchoPacket as RootEchoPak
from melobot.io import InPacket as RootInPak
from melobot.io import OutPacket as RootOutPak
from melobot.typ import SyncOrAsyncCallable

from ..const import PROTOCOL_IDENTIFIER


@dataclass(kw_only=True)
class InPacket(RootInPak):  # type: ignore[override]
    data: InputData
    protocol: str = PROTOCOL_IDENTIFIER
    finished: asyncio.Future[None]


@dataclass(kw_only=True)
class OutPacket(RootOutPak):  # type: ignore[override]
    data: OutputData
    protocol: str = PROTOCOL_IDENTIFIER


class InputType(Enum):
    STDIN = "stdin"


class OutputType(Enum):
    STDOUT_OR_STDERR = "stdout_or_stderr"
    RAW_OUTPUT = "raw_output"


class EchoType(Enum):
    pass


@dataclass(kw_only=True, frozen=True)
class InputData:
    type: InputType
    content: Any


InputDataT = TypeVar("InputDataT", bound=InputData)


@dataclass(kw_only=True, frozen=True)
class StdinInputData(InputData):
    type: Literal[InputType.STDIN] = InputType.STDIN
    content: str


@dataclass(kw_only=True, frozen=True)
class OutputData:
    type: OutputType
    content: Any


OutputDataT = TypeVar("OutputDataT", bound=OutputData)


@dataclass(kw_only=True, frozen=True)
class NormalOutputData(OutputData):
    type: OutputType = OutputType.STDOUT_OR_STDERR
    content: str
    stream: Any
    next_prompt_args: dict[str, Any] | None = None


@dataclass(kw_only=True, frozen=True)
class RawOutputData(OutputData):
    type: OutputType = OutputType.RAW_OUTPUT
    content: None = None
    executor: SyncOrAsyncCallable[[], Any]
    next_prompt_args: dict[str, Any] | None = None


@dataclass(kw_only=True, frozen=True)
class EchoData:
    type: Any = None
    content: Any = None


EchoDataT = TypeVar("EchoDataT", bound=EchoData)


@dataclass(kw_only=True)
class EchoPacket(RootEchoPak):  # type: ignore[override]
    data: EchoData = field(default_factory=EchoData)
    protocol: str = PROTOCOL_IDENTIFIER
