from dataclasses import dataclass, field

from ..handle.base import EventHandler
from ..handle.process import ProcessFlow
from ..typing import Callable, Iterable
from .ipc import AsyncShare, SyncShare


@dataclass(kw_only=True, frozen=True)
class PluginMeta:
    version: str
    shares: Iterable[SyncShare | AsyncShare] = ()
    funcs: Iterable[Callable] = ()
    flows: Iterable[ProcessFlow] = ()
    desc: str = ""
    docs: str = ""
    keywords: list[str] = field(default_factory=list)
    url: str = ""
    author: str = ""


class Plugin:
    def __init__(self, name: str, meta: PluginMeta) -> None:
        self.name = name
        self.meta = meta
        self.version = meta.version
        self.shares = tuple(meta.shares)
        self.funcs = tuple(meta.funcs)
        self.flows = tuple(meta.flows)
        self.handlers = tuple(EventHandler(self, flow) for flow in self.meta.flows)
