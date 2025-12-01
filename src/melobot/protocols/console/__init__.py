from melobot.protocols import ProtocolStack

from .adapter import *  # noqa: F403
from .const import PROTOCOL_IDENTIFIER, PROTOCOL_NAME, PROTOCOL_SUPPORT_AUTHOR, PROTOCOL_VERSION
from .handle import on_event, on_input
from .io import *  # noqa: F403


class ConsoleProtocol(ProtocolStack):
    def __init__(self, *srcs: ConsoleIO) -> None:
        super().__init__()
        if len(srcs) == 0:
            srcs = (ConsoleIO(),)
        self.adapter = Adapter()
        self.inputs = set()
        self.outputs = set()

        for src in srcs:
            if not isinstance(src, ConsoleIO):
                raise TypeError(f"不是有效的控制台源对象: {type(src)}")
            if isinstance(src, ConsoleIO):
                self.inputs.add(src)
            if isinstance(src, ConsoleIO):
                self.outputs.add(src)
