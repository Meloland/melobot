from typing_extensions import Any, Literal

from melobot.adapter import Action as RootAction
from melobot.handle import try_get_event
from melobot.typ import SyncOrAsyncCallable

from ..const import PROTOCOL_IDENTIFIER
from ..io.model import OutputType


class Action(RootAction):
    def __init__(self, type: OutputType) -> None:
        self.type = type
        super().__init__(
            protocol=PROTOCOL_IDENTIFIER,
            trigger=try_get_event(),
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(type={self.type._name_})"


class NormalOutputAction(Action):
    def __init__(
        self,
        msg: str,
        stream: Literal["stdout", "stderr"] = "stdout",
        next_prompt_args: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(OutputType.STDOUT_OR_STDERR)
        self.msg = msg
        self.is_stdout = stream == "stdout"
        self.next_prompt_args = next_prompt_args

        self._stream_flag = stream

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self._stream_flag!r}, msg_len={len(self.msg)})"


class RawOutputAction(Action):
    def __init__(
        self, executor: SyncOrAsyncCallable[[], Any], next_prompt_args: dict[str, Any] | None = None
    ) -> None:
        super().__init__(OutputType.RAW_OUTPUT)
        self.executor = executor
        self.next_prompt_args = next_prompt_args

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(executor={self.executor})"
