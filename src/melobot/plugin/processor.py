from ..log import BotLogger
from ..typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .handler import EventHandler


class ProcessFlow:
    def __init__(self, name: str) -> None:
        self.name = name
        self.blocked: bool = False

    async def run(self) -> None:
        pass
