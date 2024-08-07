from ..handle.base import EventHandler
from ..handle.process import ProcessFlow
from ..typing import BetterABC, Callable, Iterable, abstractattr
from .ipc import AsyncShare, SyncShare


class Plugin(BetterABC):
    version: str = abstractattr()
    shares: Iterable[SyncShare | AsyncShare] = ()
    funcs: Iterable[Callable] = ()
    flows: Iterable[ProcessFlow] = ()
    desc: str = ""
    docs: str = ""
    keywords: list[str] = []
    url: str = ""
    author: str = ""

    def _build(self, name: str) -> None:
        self.name = name
        self.handlers = tuple(EventHandler(self, flow) for flow in self.flows)
