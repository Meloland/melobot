from dataclasses import dataclass, field

from melobot.io import EchoPacket as RootEchoPak
from melobot.io import InPacket as RootInPack
from melobot.io import OutPacket as RootOutPak

from ..const import PROTOCOL_IDENTIFIER


@dataclass(frozen=True, kw_only=True)
class InPacket(RootInPack):
    data: dict
    protocol: str = PROTOCOL_IDENTIFIER


@dataclass(frozen=True, kw_only=True)
class OutPacket(RootOutPak):
    data: str
    action_type: str
    action_params: dict
    echo_id: str | None = None
    protocol: str = PROTOCOL_IDENTIFIER


@dataclass(frozen=True, kw_only=True)
class EchoPacket(RootEchoPak):
    action_type: str = ""
    data: dict = field(default_factory=dict)
    protocol: str = PROTOCOL_IDENTIFIER
