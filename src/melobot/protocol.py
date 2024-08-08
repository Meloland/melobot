from dataclasses import dataclass

from .adapter.base import Adapter
from .io.base import AbstractInSource, AbstractOutSource
from .typing import Sequence


@dataclass(kw_only=True, frozen=True)
class ProtocolStack:
    inputs: Sequence[AbstractInSource]
    outputs: Sequence[AbstractOutSource]
    adapters: Adapter
