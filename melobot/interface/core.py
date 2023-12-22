from abc import ABC, abstractmethod
from asyncio import Future

from ..models.action import BotAction
from ..models.event import BotEvent, MetaEvent, RespEvent


class IRespDispatcher(ABC):
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    async def dispatch(self, resp: RespEvent) -> None:
        pass


class IActionSender(ABC):
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    async def send(self, action: BotAction) -> None:
        pass


class IActionResponder(ABC):
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    async def take_action(self, action: BotAction) -> None:
        pass

    @abstractmethod
    async def take_action_wait(self, action: BotAction) -> Future[RespEvent]:
        pass


class IMetaDispatcher(ABC):
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    async def dispatch(self, meta_event: MetaEvent) -> None:
        pass


class IEventDispatcher(ABC):
    def __init__(self) -> None:
        super().__init__()
    
    @abstractmethod
    async def dispatch(self, event: BotEvent) -> None:
        pass
