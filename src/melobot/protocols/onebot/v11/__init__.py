from melobot.protocols import ProtocolStack

from .. import __version__
from .adapter import *  # noqa: F403
from .const import PROTOCOL_IDENTIFIER, PROTOCOL_NAME, PROTOCOL_SUPPORT_AUTHOR, PROTOCOL_VERSION
from .handle import (
    on_at_qq,
    on_downstream_call,
    on_event,
    on_message,
    on_meta,
    on_notice,
    on_request,
    on_upstream_ret,
)
from .io import *  # noqa: F403
from .utils import *  # noqa: F403


class OneBotV11Protocol(ProtocolStack):
    def __init__(self, *srcs: BaseIOSource) -> None:
        super().__init__()
        self.adapter = Adapter()
        self.inputs = set()
        self.outputs = set()

        for src in srcs:
            if not isinstance(src, BaseIOSource):
                raise TypeError(f"不支持的 OneBot v11 源类型: {type(src)}")
            self.inputs.add(src)
            self.outputs.add(src)
