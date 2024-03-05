from abc import ABC, abstractmethod
from asyncio import Future

from ..models.action import BotAction
from ..models.event import BotEvent, ResponseEvent


class AbstractSender(ABC):
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    async def send(self, action: BotAction) -> None:
        pass


class AbstractResponder(ABC):
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    async def dispatch(self, resp: ResponseEvent) -> None:
        pass

    @abstractmethod
    async def take_action(self, action: BotAction) -> None:
        pass

    @abstractmethod
    async def take_action_wait(self, action: BotAction) -> Future[ResponseEvent]:
        pass


class AbstractDispatcher(ABC):
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    async def dispatch(self, event: BotEvent) -> None:
        pass
