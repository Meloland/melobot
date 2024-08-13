from .adapter.base import Adapter
from .io.base import AbstractInSource, AbstractOutSource
from .typ import BetterABC, Sequence, abstractattr


class Protocol(BetterABC):
    inputs: Sequence[AbstractInSource] = abstractattr()
    outputs: Sequence[AbstractOutSource] = abstractattr()
    adapter: Adapter = abstractattr()
