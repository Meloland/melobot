from abc import ABC, abstractmethod

from ..models.event import BotEvent
from ..interface.utils import *
from ..models.session import SessionRule
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
    def verify(self, event: BotEvent) -> bool:
        """
        前置校验逻辑，包含权限校验、尝试匹配和尝试解析
        """
        pass

    @abstractmethod
    async def handle(self, event: BotEvent) -> bool:
        """
        校验通过后的处理方法。
        此处应该进行 session 建立和超时控制等一系列操作，然后再运行内部绑定的处理逻辑
        """
        pass


class IHookRunner(ABC):
    def __init__(self) -> None:
        super().__init__()


IEventExecutor = Callable[[None], Coroutine[Any, Any, None]]

IHookCaller = Callable[[None], Coroutine[Any, Any, None]]


class ExecutorWrapper:
    """
    包装器
    """
    def __init__(self, type: str, executor: IEventExecutor, params: List[Any]) -> None:
        self.type = type
        self.executor = executor
        self.params = params


class CallerWrapper:
    """
    包装器
    """
    def __init__(self, type: str, caller: IHookCaller, params: List[Any]) -> None:
        self.type = type
        self.caller = caller
        self.params = params


class PluginTemplate(ABC):
    """
    插件模板。
    外部所有插件应该继承该类并实现
    """
    def __init__(self) -> None:
        super().__init__()
        self.name: str = None
        self.version: str = None
        self.executors: List[ExecutorWrapper] = None
        self.callers: List[CallerWrapper] = None

        self.rw_auth: bool=False
        self.call_auth: bool=False
        self.store: Dict[str, Any]={}


class IBotPlugin(ABC):
    """
    bot 插件抽象
    """
    def __init__(self) -> None:
        super().__init__()
        self.name: str
        self.version: str=None
        self.rw_auth: bool=False
        self.call_auth: bool=False
        self.store: Dict[str, Any]={}
        self.handlers: List[IEventHandler]=None
        self.runners: List[IHookRunner]=None


class BotPluginType:
    """
    bot 插件 typing
    """
    def __init__(self) -> None:
        super().__init__()
        self.name: str
        self.version: str
        self.rw_auth: bool
        self.call_auth: bool
        self.store: Dict[str, Any]
        self.handlers: List[IEventHandler]
        self.runners: List[IHookRunner]

    def at_message(self, matcher: BotMatcher=None, parser: BotParser=None, checker: BotChecker=None, priority: int=PriorityLevel.MEAN, 
                   timeout: int=None, set_block: bool=False, temp: bool=False, session_rule: SessionRule=None, 
                   conflict_wait: bool=False, conflict_callback: Callable[[None], Coroutine]=None, 
                   overtime_callback: Callable[[None], Coroutine]=None
                   ) -> Callable[[IEventExecutor], ExecutorWrapper]:
        """
        作为 typing 使用
        """
        pass