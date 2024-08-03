from dataclasses import dataclass, field

from ..handle.process import ProcessFlow
from ..typing import Callable, Iterable
from .ipc import AsyncShare, SyncShare


class Plugin:
    def __init__(self) -> None:
        self.name: str


@dataclass(kw_only=True, frozen=True)
class PluginMetaData:
    name: str
    version: str
    shares: Iterable[SyncShare | AsyncShare] = ()
    funcs: Iterable[Callable] = ()
    flows: Iterable[ProcessFlow] = ()
    desc: str = ""
    docs: str = ""
    keywords: list[str] = field(default_factory=list)
    url: str = ""
    author: str = ""
