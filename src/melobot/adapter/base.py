from __future__ import annotations

import asyncio
from asyncio import create_task
from contextlib import AsyncExitStack, _GeneratorContextManager, asynccontextmanager
from enum import Enum
from os import PathLike
from typing import (
    TYPE_CHECKING,
    AsyncGenerator,
    Callable,
    Generic,
    Iterable,
    NoReturn,
    Sequence,
    cast,
    final,
)

from typing_extensions import LiteralString, Self, TypeVar

from .._hook import HookBus
from ..ctx import EventBuildInfo, EventBuildInfoCtx, LoggerCtx, OutSrcFilterCtx
from ..exceptions import AdapterError
from ..io.base import (
    AbstractInSource,
    AbstractOutSource,
    EchoPacketT,
    InPacketT,
    InSourceT,
    OutPacketT,
    OutSourceT,
)
from ..log.base import LogLevel
from ..typ import AsyncCallable, BetterABC, P, abstractmethod
from .content import Content
from .model import ActionHandle, ActionT, EchoT, Event, EventT

if TYPE_CHECKING:
    from ..bot.dispatch import Dispatcher


_EVENT_BUILD_INFO_CTX = EventBuildInfoCtx()
_OUT_SRC_FILTER_CTX = OutSrcFilterCtx()


class AbstractEventFactory(BetterABC, Generic[InPacketT, EventT]):
    """抽象事件工厂类"""

    @abstractmethod
    async def create(self, packet: InPacketT) -> EventT:
        """将 :class:`.InPacket` 对象转换为 :class:`.Event` 对象的方法

        :param packet: 输入包
        :return: 事件
        """
        raise NotImplementedError


EventFactoryT = TypeVar("EventFactoryT", bound=AbstractEventFactory)


class AbstractOutputFactory(BetterABC, Generic[OutPacketT, ActionT]):
    """抽象输出工厂类"""

    @abstractmethod
    async def create(self, action: ActionT) -> OutPacketT:
        """将 :class:`.Action` 对象转换为 :class:`.OutPacket` 对象的方法

        :param packet: 行为
        :return: 输出包
        """
        raise NotImplementedError


OutputFactoryT = TypeVar("OutputFactoryT", bound=AbstractOutputFactory)


class AbstractEchoFactory(BetterABC, Generic[EchoPacketT, EchoT]):
    """抽象回应工厂类"""

    @abstractmethod
    async def create(self, packet: EchoPacketT) -> EchoT | None:
        """将 :class:`.EchoPacket` 对象转换为 :class:`.Echo` 对象的方法

        :param packet: 回应包
        :return: 回应或空值
        """
        raise NotImplementedError


EchoFactoryT = TypeVar("EchoFactoryT", bound=AbstractEchoFactory)


class AdapterLifeSpan(Enum):
    """适配器生命周期阶段的枚举"""

    BEFORE_EVENT = "be"
    BEFORE_ACTION = "ba"
    STARTED = "sta"
    STOPPED = "sto"


class Adapter(
    BetterABC,
    Generic[
        EventFactoryT,
        OutputFactoryT,
        EchoFactoryT,
        ActionT,
        InSourceT,
        OutSourceT,
    ],
):
    """适配器基类

    :ivar LiteralString protocol: 适配器所使用的协议
    """

    # pylint: disable=duplicate-code
    # pylint: disable=unused-argument

    def __init__(
        self,
        protocol: LiteralString,
        event_factory: EventFactoryT,
        output_factory: OutputFactoryT,
        echo_factory: EchoFactoryT,
    ) -> None:
        super().__init__()
        self.protocol = protocol

        self.in_srcs: list[InSourceT] = []
        self.out_srcs: list[OutSourceT] = []
        self.dispatcher: "Dispatcher"
        self._event_factory = event_factory
        self._output_factory = output_factory
        self._echo_factory = echo_factory

        self._inited = False
        self._life_bus = HookBus[AdapterLifeSpan](AdapterLifeSpan)

    @final
    def on(
        self, *periods: AdapterLifeSpan
    ) -> Callable[[AsyncCallable[P, None]], AsyncCallable[P, None]]:
        """生成注册适配器生命周期回调的装饰器

        :param periods: 要绑定的生命周期阶段

        :return: 装饰器
        """

        def wrapped(func: AsyncCallable[P, None]) -> AsyncCallable[P, None]:
            for type in periods:
                self._life_bus.register(type, func)
            return func

        return wrapped

    @final
    def get_isrcs(self, filter: Callable[[InSourceT], bool]) -> set[InSourceT]:
        """获取与当前适配器匹配的所有输入源

        :param filter: 过滤函数，为 `True` 时保留输入源
        :return: 输入源的集合
        """
        return set(src for src in self.in_srcs if filter(src))

    @final
    def get_osrcs(self, filter: Callable[[OutSourceT], bool]) -> set[OutSourceT]:
        """获取与当前适配器匹配的所有输出源

        :param filter: 过滤函数，为 `True` 时保留输出源
        :return: 输出源的集合
        """
        return set(src for src in self.out_srcs if filter(src))

    @final
    async def __adapter_input_loop__(self, src: InSourceT) -> NoReturn:
        logger = LoggerCtx().get()
        while True:
            try:
                packet = await src.input()
                event = await self._event_factory.create(packet)
                with _EVENT_BUILD_INFO_CTX.in_ctx(EventBuildInfo(self, src)):
                    await self._life_bus.emit(
                        AdapterLifeSpan.BEFORE_EVENT, wait=True, args=(event,)
                    )
                    asyncio.create_task(self.dispatcher.broadcast(event))
            except Exception:
                logger.exception(f"适配器 {self} 处理输入与分发事件时发生异常")
                logger.generic_obj("异常点局部变量：", locals(), level=LogLevel.ERROR)

    @asynccontextmanager
    @final
    async def __adapter_launch__(self) -> AsyncGenerator[Self, None]:
        if self._inited:
            raise AdapterError(f"适配器 {self} 已在运行，不能重复启动")

        try:
            async with AsyncExitStack() as stack:
                out_src_ts = tuple(
                    create_task(stack.enter_async_context(src)) for src in self.out_srcs
                )
                if len(out_src_ts):
                    await asyncio.wait(out_src_ts)

                in_src_ts = tuple(
                    create_task(stack.enter_async_context(src))
                    for src in self.in_srcs
                    if not src.opened()
                )
                if len(in_src_ts):
                    await asyncio.wait(in_src_ts)

                for src in self.in_srcs:
                    create_task(self.__adapter_input_loop__(src))

                self._inited = True
                await self._life_bus.emit(AdapterLifeSpan.STARTED)
                yield self

        finally:
            if self._inited:
                await self._life_bus.emit(AdapterLifeSpan.STOPPED, wait=True)

    @final
    def filter_out(
        self, filter: Callable[[OutSourceT], bool]
    ) -> _GeneratorContextManager[None]:
        """上下文管理器，提供由 `filter` 控制输出的输出上下文

        :param filter: 过滤函数，为 `True` 时允许该输出源输出
        """
        return _OUT_SRC_FILTER_CTX.in_ctx(filter)

    async def call_output(self, action: ActionT) -> tuple[ActionHandle, ...]:
        """输出行为，并返回各个输出源返回的 :class:`.ActionHandle` 组成的元组

        适配器开发者的适配器子类可以重写此方法，以实现自定义功能

        但子类实现中必须调用原始方法： `super().call_output(...)`

        :param action: 行为
        :return: :class:`.ActionHandle` 元组
        """
        osrcs: Iterable[OutSourceT]
        filter = _OUT_SRC_FILTER_CTX.try_get()
        cur_isrc: AbstractInSource | None
        if info := _EVENT_BUILD_INFO_CTX.try_get():
            cur_isrc = info.in_src
        else:
            cur_isrc = None

        if filter is not None:
            osrcs = (osrc for osrc in self.out_srcs if filter(osrc))
        elif isinstance(cur_isrc, AbstractOutSource):
            osrcs = (cast(OutSourceT, cur_isrc),)
        else:
            osrcs = (self.out_srcs[0],) if len(self.out_srcs) else ()

        await self._life_bus.emit(
            AdapterLifeSpan.BEFORE_ACTION, wait=True, args=(action,)
        )
        return tuple(
            ActionHandle(action, osrc, self._output_factory, self._echo_factory)
            for osrc in osrcs
        )

    @abstractmethod
    async def send_text(self, text: str) -> tuple[ActionHandle, ...]:
        """输出文本

        抽象方法。所有适配器子类应该实现此方法

        :param text: 文本
        :return: :class:`.ActionHandle` 元组
        """
        raise NotImplementedError

    async def send_media(
        self,
        name: str,
        raw: bytes | None = None,
        url: str | None = None,
        mimetype: str | None = None,
    ) -> tuple[ActionHandle, ...]:
        """输出多媒体内容

        建议所有适配器子类重写此方法，否则回退到基类实现：仅使用 :func:`send_text` 输出相关提示信息

        :param name: 多媒体内容的名称
        :param raw: 多媒体内容的二进制内容
        :param url: 多媒体内容的网络地址（和 `raw` 参数二选一）
        :param mimetype: 多媒体内容的 mimetype，为空则根据 `name` 自动检测
        :return: :class:`.ActionHandle` 元组
        """
        return await self.send_text(
            f"[melobot media: {name if url is None else name + ' at ' + url}]"
        )

    async def send_image(
        self,
        name: str,
        raw: bytes | None = None,
        url: str | None = None,
        mimetype: str | None = None,
    ) -> tuple[ActionHandle, ...]:
        """输出图像内容

        建议所有适配器子类重写此方法，否则回退到基类实现：仅使用 :func:`send_text` 输出相关提示信息

        :param name: 图像内容的名称
        :param raw: 图像内容的二进制内容
        :param url: 图像内容的网络地址（和 `raw` 参数二选一）
        :param mimetype: 图像内容的 mimetype，为空则根据 `name` 自动检测
        :return: :class:`.ActionHandle` 元组
        """
        return await self.send_text(
            f"[melobot image: {name if url is None else name + ' at ' + url}]"
        )

    async def send_audio(
        self,
        name: str,
        raw: bytes | None = None,
        url: str | None = None,
        mimetype: str | None = None,
    ) -> tuple[ActionHandle, ...]:
        """输出音频内容

        建议所有适配器子类重写此方法，否则回退到基类实现：仅使用 :func:`send_text` 输出相关提示信息

        :param name: 音频内容的名称
        :param raw: 音频内容的二进制内容
        :param url: 音频内容的网络地址（和 `raw` 参数二选一）
        :param mimetype: 音频内容的 mimetype，为空则根据 `name` 自动检测
        :return: :class:`.ActionHandle` 元组
        """
        return await self.send_text(
            f"[melobot audio: {name if url is None else name + ' at ' + url}]"
        )

    async def send_voice(
        self,
        name: str,
        raw: bytes | None = None,
        url: str | None = None,
        mimetype: str | None = None,
    ) -> tuple[ActionHandle, ...]:
        """输出语音内容

        建议所有适配器子类重写此方法，否则回退到基类实现：仅使用 :func:`send_text` 输出相关提示信息

        :param name: 语音内容的名称
        :param raw: 语音内容的二进制内容
        :param url: 语音内容的网络地址（和 `raw` 参数二选一）
        :param mimetype: 语音内容的 mimetype，为空则根据 `name` 自动检测
        :return: :class:`.ActionHandle` 元组
        """
        return await self.send_text(
            f"[melobot voice: {name if url is None else name + ' at ' + url}]"
        )

    async def send_video(
        self,
        name: str,
        raw: bytes | None = None,
        url: str | None = None,
        mimetype: str | None = None,
    ) -> tuple[ActionHandle, ...]:
        """输出视频内容

        建议所有适配器子类重写此方法，否则回退到基类实现：仅使用 :func:`send_text` 输出相关提示信息

        :param name: 视频内容的名称
        :param raw: 视频内容的二进制内容
        :param url: 视频内容的网络地址（和 `raw` 参数二选一）
        :param mimetype: 视频内容的 mimetype，为空则根据 `name` 自动检测
        :return: :class:`.ActionHandle` 元组
        """
        return await self.send_text(
            f"[melobot video: {name if url is None else name + ' at ' + url}]"
        )

    async def send_file(
        self, name: str, path: str | PathLike[str]
    ) -> tuple[ActionHandle, ...]:
        """输出文件

        建议所有适配器子类重写此方法，否则回退到基类实现：仅使用 :func:`send_text` 输出相关提示信息

        :param name: 文件名
        :param path: 文件路径
        :return: :class:`.ActionHandle` 元组
        """
        return await self.send_text(f"[melobot file: {name} at {path}]")

    async def send_refer(
        self, event: Event, contents: Sequence[Content] | None = None
    ) -> tuple[ActionHandle, ...]:
        """输出对过往事件的引用

        建议所有适配器子类重写此方法，否则回退到基类实现：仅使用 :func:`send_text` 输出相关提示信息

        :param event: 过往的事件对象
        :param contents: 附加的通用内容序列
        :return: :class:`.ActionHandle` 元组
        """
        return await self.send_text(
            f"[melobot refer: {event.__class__.__name__}({event.id})]"
        )

    async def send_resource(self, name: str, url: str) -> tuple[ActionHandle, ...]:
        """输出网络资源

        建议所有适配器子类重写此方法，否则回退到基类实现：仅使用 :func:`send_text` 输出相关提示信息

        :param name: 网络资源名称
        :param url: 网络资源的 url
        :return: :class:`.ActionHandle` 元组
        """
        return await self.send_text(f"[melobot resource: {name} at {url}]")
