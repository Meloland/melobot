from typing import Iterable

from ..handle.base import EventHandler
from ..handle.process import Flow
from ..typ import BetterABC, Callable, abstractattr
from .ipc import AsyncShare, SyncShare


class Plugin(BetterABC):
    version: str = abstractattr()
    shares: Iterable[SyncShare | AsyncShare] = ()
    funcs: Iterable[Callable] = ()
    flows: Iterable[Flow] = ()
    desc: str = ""
    docs: str = ""
    keywords: list[str] = []
    url: str = ""
    author: str = ""

    def __init__(self) -> None:
        super().__init__()
        self.name: str
        self.handlers: tuple[EventHandler, ...]

    def build(self, name: str) -> None:
        self.name = name
        self.handlers = tuple(EventHandler(self, flow) for flow in self.flows)
