from __future__ import annotations

import time
from abc import abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from types import TracebackType

from typing_extensions import Any, Callable, Generic, LiteralString, Self, TypeVar

from ..mixin import HookMixin
from ..typ.base import AsyncCallable, P, SyncOrAsyncCallable
from ..typ.cls import BetterABC, abstractattr
from ..utils.common import get_id


@dataclass
class InPacket:
    """输入包基类（数据类）

    :ivar float time: 时间戳
    :ivar str id: id 标识
    :ivar typing.LiteralString | None protocol: 遵循的协议
    :ivar Any data: 附加的数据
    """

    time: float = field(default_factory=lambda: time.time_ns() / 1e9)
    id: str = field(default_factory=get_id)
    protocol: LiteralString | None = None
    data: Any = None


@dataclass
class OutPacket:
    """输出包基类（数据类）

    :ivar float time: 时间戳
    :ivar str id: id 标识
    :ivar typing.LiteralString | None protocol: 遵循的协议
    :ivar Any data: 附加的数据
    """

    time: float = field(default_factory=lambda: time.time_ns() / 1e9)
    id: str = field(default_factory=get_id)
    protocol: LiteralString | None = None
    data: Any = None


@dataclass
class EchoPacket:
    """回应包基类（数据类）

    :ivar float time: 时间戳
    :ivar str id: id 标识
    :ivar typing.LiteralString | None protocol: 遵循的协议
    :ivar Any data: 附加的数据
    :ivar bool ok: 回应是否成功
    :ivar int status: 回应状态码
    :ivar str prompt: 提示语
    :ivar bool noecho: 是否并无回应产生
    """

    time: float = field(default_factory=lambda: time.time_ns() / 1e9)
    id: str = field(default_factory=get_id)
    protocol: LiteralString | None = None
    data: Any = None
    ok: bool = True
    status: int = 0
    prompt: str = ""
    noecho: bool = False


InPacketT = TypeVar("InPacketT", bound=InPacket)
OutPacketT = TypeVar("OutPacketT", bound=OutPacket)
EchoPacketT = TypeVar("EchoPacketT", bound=EchoPacket)


class SourceLifeSpan(Enum):
    """源生命周期阶段的枚举"""

    #: 源启动完成之后
    STARTED = "sta"
    #: 源重新启动完成之后（未实现重启的源，自然不会调用这个）
    RESTARTED = "res"
    #: 源停止操作发生前（出现异常可能不会调用此类型），具体何时触发请参考具体的源实现（例如一些源重启前发出此信号，但其他一些源则不一定）
    CLOSE = "clo"
    #: bot 关闭时触发的源对象停止。可以在这里安全地运行清理操作
    STOPPED = "sto"


class AbstractSource(HookMixin[SourceLifeSpan], BetterABC):
    """抽象源基类"""

    protocol: LiteralString = abstractattr()

    def __init__(self) -> None:
        super().__init__(
            hook_type=SourceLifeSpan,
            hook_tag=f"{self.__class__.__module__}.{self.__class__.__name__}",
        )

    @abstractmethod
    async def open(self) -> None:
        """源打开方法"""
        raise NotImplementedError

    @abstractmethod
    def opened(self) -> bool:
        """源是否已打开"""
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """源关闭方法"""
        raise NotImplementedError

    async def __aenter__(self) -> Self:
        if self.opened():
            return self

        await self.open()
        await self._hook_bus.emit(SourceLifeSpan.STARTED)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        try:
            if not self.opened():
                return None
            await self._hook_bus.emit(SourceLifeSpan.CLOSE, True)
            await self.close()
        finally:
            await self._hook_bus.emit(SourceLifeSpan.STOPPED, True)
        return None

    @property
    def on_started(self) -> Callable[[SyncOrAsyncCallable[P, None]], AsyncCallable[P, None]]:
        """给源注册 :obj:`.SourceLifeSpan.STARTED` 阶段 hook 的装饰器"""
        return self.on(SourceLifeSpan.STARTED)

    @property
    def on_restarted(self) -> Callable[[SyncOrAsyncCallable[P, None]], AsyncCallable[P, None]]:
        """给源注册 :obj:`.SourceLifeSpan.RESTARTED` 阶段 hook 的装饰器"""
        return self.on(SourceLifeSpan.RESTARTED)

    @property
    def on_close(self) -> Callable[[SyncOrAsyncCallable[P, None]], AsyncCallable[P, None]]:
        """给源注册 :obj:`.SourceLifeSpan.CLOSE` 阶段 hook 的装饰器"""
        return self.on(SourceLifeSpan.CLOSE)

    @property
    def on_stopped(self) -> Callable[[SyncOrAsyncCallable[P, None]], AsyncCallable[P, None]]:
        """给源注册 :obj:`.SourceLifeSpan.STOPPED` 阶段 hook 的装饰器"""
        return self.on(SourceLifeSpan.STOPPED)


class AbstractInSource(AbstractSource, Generic[InPacketT]):
    """抽象输入源基类"""

    @abstractmethod
    async def open(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def opened(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def input(self) -> InPacketT:
        """源输入方法

        :return: 返回 :class:`.InPacket` 对象
        """
        raise NotImplementedError


InSourceT = TypeVar("InSourceT", bound=AbstractInSource)


class AbstractOutSource(AbstractSource, Generic[OutPacketT, EchoPacketT]):
    """抽象输出源基类"""

    @abstractmethod
    async def open(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def opened(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def output(self, packet: OutPacketT) -> EchoPacketT:
        """源输出方法

        :return: 返回 :class:`.OutPacket` 对象
        """
        raise NotImplementedError


OutSourceT = TypeVar("OutSourceT", bound=AbstractOutSource)

InOrOutSourceT = TypeVar("InOrOutSourceT", bound=AbstractInSource | AbstractOutSource)


class AbstractIOSource(AbstractInSource[InPacketT], AbstractOutSource[OutPacketT, EchoPacketT]):
    """抽象输入输出源基类"""

    @abstractmethod
    async def open(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def opened(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def input(self) -> InPacketT:
        raise NotImplementedError

    @abstractmethod
    async def output(self, packet: OutPacketT) -> EchoPacketT:
        raise NotImplementedError


IOSourceT = TypeVar("IOSourceT", bound=AbstractIOSource)
