from .adapter.base import Adapter
from .io.base import AbstractInSource, AbstractOutSource
from .typing import BetterABC, Sequence, abstractattr


class ProtocolStack(BetterABC):
    inputs: Sequence[AbstractInSource] = abstractattr()
    outputs: Sequence[AbstractOutSource] = abstractattr()
    adapters: Adapter = abstractattr()
