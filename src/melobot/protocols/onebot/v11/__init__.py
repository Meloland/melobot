from melobot.protocols import ProtocolStack
from melobot.utils.common import DeprecatedLoader as _DeprecatedLoader

from .. import __version__
from .adapter import *
from .const import (
    PROTOCOL_IDENTIFIER,
    PROTOCOL_NAME,
    PROTOCOL_SUPPORT_AUTHOR,
    PROTOCOL_VERSION,
)
from .handle import _LOADER as _HANDLE_LOADER
from .handle import on_at_qq, on_event, on_message, on_meta, on_notice, on_request
from .io import *
from .utils import _LOADER as _UTILS_LOADER
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


_LOADER = _DeprecatedLoader.merge(__name__, _HANDLE_LOADER, _UTILS_LOADER)


def __getattr__(name: str) -> Any:
    return _LOADER.get(name)
