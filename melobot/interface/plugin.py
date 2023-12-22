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
        接收总线分发的事件的方法。返回校验结果，便于 disptacher 进行优先级阻断。校验通过会自动处理事件。
        """
        pass


class IHookRunner(ABC):
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    async def run(self) -> None:
        pass

# TODO: executor 和 hookcaller 改为命名元组
# TODO: hookcaller 改名为 hook
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
        self.version: str = '1.0.0'
        self.executors: List[Tuple[IEventExecutor, IEventHandler, List[str]]] = []
        self.callers: List[Tuple[IHookCaller, IHookRunner, List[str]]] = []

        self.rw_auth: bool=False
        self.call_auth: bool=False
        self.store: Dict[str, Any]={}
