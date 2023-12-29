from abc import ABC, abstractmethod, abstractproperty

from .typing import *


class BotEvent(ABC):
    """
    Bot 事件类
    """
    def __init__(self, rawEvent: dict) -> None:
        self.raw = rawEvent
        self._args_map: Dict[object, List[ParseArgs]]

    def _store_args(self, handler: object, args: List[ParseArgs]) -> None:
        if not hasattr(self, '_args_map'):
            self._args_map = {}
        self._args_map[handler] = args

    @abstractproperty
    def time(self) -> int: pass
    @abstractproperty
    def type(self) -> str: pass
    
    def is_msg(self) -> bool: return self.type == "message"
    def is_req(self) -> bool: return self.type == "request"
    def is_notice(self) -> bool: return self.type == "notice"
    def is_meta(self) -> bool: return self.type == "meta"
    def is_resp(self) -> bool: return self.type == "response"


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


# 事件方法（事件执行器）构造参数
HandlerArgs = NamedTuple('HandlerArgs', executor=AsyncFunc[None], type=IEventHandler, params=List[Any])
# 钩子方法（插件钩子）构造参数
RunnerArgs = NamedTuple('RunnerArgs', hook_func=AsyncFunc[None], type=IHookRunner, params=List[Any])
# 插件共享对象构造参数
ShareObjArgs = NamedTuple('ShareObjArgs', property=str, namespace=str, id=str)
# 插件共享对象回调的构造参数
ShareCbArgs = NamedTuple('ShareCbArgs', namespace=str, id=str, cb=Callable)
# 插件信号方法构造参数
SignalHandlerArgs = NamedTuple('SignalHandlerArgs', func=AsyncFunc[None], type=str)