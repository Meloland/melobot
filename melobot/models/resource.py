import time
from abc import ABC, abstractmethod
from asyncio import iscoroutine

from ..interface.typing import *


class ResourceLoader(ABC):
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    def load(self) -> object:
        pass


class ResourceDisposer(ABC):
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    def dispose(self, resource: object) -> None:
        pass


class BotResource:
    """
    bot 资源结点。
    指定资源的值，或指定加载或释放方法（可为异步或同步）
    """
    def __init__(self, value: object=None, loader: ResourceLoader=None, disposer: ResourceDisposer=None) -> None:
        self.crt_time = time.time()
        self.value = value
        self._loader = loader
        self._disposer = disposer
        
        self.disposed = False
        self.loaded = False

    async def load(self) -> None:
        """
        加载资源
        """
        if self.loaded == False:
            if self._loader:
                res = self._loader.load()
                if iscoroutine(res):
                    await res
                self.value = res
                self.loaded = True
            else:
                self.loaded = True

    async def dispose(self) -> None:
        """
        释放资源
        """
        if self.disposed == False:
            if self._disposer:
                res = self._disposer.dispose(self.value)
                if iscoroutine(res):
                    await res
                self.value = None
                self.disposed = True
            else:
                self.value = None
                self.disposed = True
