from dataclasses import dataclass, field

from melobot.io import EchoPacket as RootEchoPak
from melobot.io import InPacket as RootInPak
from melobot.io import OutPacket as RootOutPak

from ..const import PROTOCOL_IDENTIFIER


@dataclass(kw_only=True)
class InPacket(RootInPak):
    """OneBot v11 输入包

    :ivar dict data: 事件原始字典
    """

    data: dict
    protocol: str = PROTOCOL_IDENTIFIER


@dataclass(kw_only=True)
class OutPacket(RootOutPak):
    data: str
    action_type: str
    action_params: dict
    echo_id: str | None = None
    protocol: str = PROTOCOL_IDENTIFIER


@dataclass(kw_only=True)
class EchoPacket(RootEchoPak):
    action_type: str = ""
    data: dict = field(default_factory=dict)
    protocol: str = PROTOCOL_IDENTIFIER
