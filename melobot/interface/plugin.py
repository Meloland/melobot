from abc import ABC, abstractmethod

from ..models.event import BotEvent
from .utils import *
from .typing import *


class IEventHandler(ABC):
    def __init__(self, priority: int=1, timeout: float=None, set_block: bool=False, temp: bool=False) -> None:
        super().__init__()
        self.set_block = set_block
        self.timeout = timeout
        self.priority = priority

        self.is_temp = temp
        self.is_valid = True

    @abstractmethod
    def _verify(self, event: BotEvent) -> bool:
        """
        前置校验逻辑，包含权限校验、尝试匹配和尝试解析
        """
        pass

    @abstractmethod
    async def evoke(self, event: BotEvent) -> bool:
        """
        接收总线分发的事件的方法。
        此处应该进行校验、 session 建立和超时控制等一系列操作，然后再运行内部绑定的处理逻辑
        """
        pass


class IHookRunner(ABC):
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    async def run(self) -> None:
        pass


IEventExecutor = Callable[[None], Coroutine[Any, Any, None]]

IHookCaller = Callable[[None], Coroutine[Any, Any, None]]


class PluginTemplate(ABC):
    """
    插件模板。
    外部所有插件应该继承该类并实现
    """
    def __init__(self) -> None:
        super().__init__()
        self.name: str = None
        self.version: str = None
        self.executors: List[Tuple[IEventExecutor, IEventHandler, List[str]]] = None
        self.callers: List[Tuple[IHookCaller, IHookRunner, List[str]]] = None

        self.rw_auth: bool=False
        self.call_auth: bool=False
        self.store: Dict[str, Any]={}
