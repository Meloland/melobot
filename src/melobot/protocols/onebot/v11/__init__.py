from melobot.protocols import ProtocolStack

from .. import __version__
from .adapter import *
from .const import (
    PROTOCOL_IDENTIFIER,
    PROTOCOL_NAME,
    PROTOCOL_SUPPORT_AUTHOR,
    PROTOCOL_VERSION,
)
from .handle import (
    DefaultRule,
    GetParseArgs,
    on_at_qq,
    on_command,
    on_contain_match,
    on_end_match,
    on_event,
    on_full_match,
    on_message,
    on_meta,
    on_notice,
    on_regex_match,
    on_request,
    on_start_match,
)
from .io import *
from .utils import *


class OneBotV11Protocol(ProtocolStack):
    def __init__(self, *srcs: BaseSource) -> None:
        super().__init__()
        self.adapter = Adapter()
        self.inputs = set()
        self.outputs = set()

        for src in srcs:
            if not isinstance(src, BaseSource):
                raise TypeError(f"不支持的 OneBot v11 源类型: {type(src)}")
            if isinstance(src, BaseInSource):
                self.inputs.add(src)
            if isinstance(src, BaseOutSource):
                self.outputs.add(src)
