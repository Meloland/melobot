from typing import Sequence

from .adapter.base import Adapter
from .io.base import AbstractInSource, AbstractOutSource
from .typ import BetterABC, abstractattr


class ProtocolStack(BetterABC):
    inputs: Sequence[AbstractInSource] = abstractattr()
    outputs: Sequence[AbstractOutSource] = abstractattr()
    adapter: Adapter = abstractattr()
