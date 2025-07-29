from __future__ import annotations

import asyncio
from abc import abstractmethod
from asyncio import create_task
from contextlib import AsyncExitStack, _GeneratorContextManager, asynccontextmanager
from enum import Enum
from os import PathLike

from typing_extensions import (
    TYPE_CHECKING,
    AsyncGenerator,
    Callable,
    Generic,
    Iterable,
    LiteralString,
    NoReturn,
    Self,
    Sequence,
    TypeVar,
    cast,
    final,
)

from ..ctx import EventOrigin, FlowCtx, OutSrcFilterCtx
from ..exceptions import AdapterError
from ..io.base import (
    AbstractInSource,
    AbstractOutSource,
    AbstractSource,
    EchoPacketT,
    InPacketT,
    InSourceT,
    OutPacketT,
    OutSourceT,
)
from ..log import log_exc
from ..mixin import HookMixin
from ..typ.cls import BetterABC
from .content import Content
from .model import ActionHandle, ActionHandleGroup, ActionT, EchoT, Event, EventT

if TYPE_CHECKING:
    from ..bot.dispatch import Dispatcher


_OUT_SRC_FILTER_CTX = OutSrcFilterCtx()
_FLOW_CTX = FlowCtx()


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

    BEFORE_EVENT_HANDLE = "beh"
    BEFORE_ACTION_EXEC = "bae"
    STARTED = "sta"
    CLOSE = "clo"
    STOPPED = "sto"


class Adapter(
    HookMixin[AdapterLifeSpan],
    Generic[
        EventFactoryT,
        OutputFactoryT,
        EchoFactoryT,
        ActionT,
        InSourceT,
        OutSourceT,
    ],
    BetterABC,
):
    """适配器基类

    :ivar LiteralString protocol: 适配器所使用的协议
    """

    def __init__(
        self,
        protocol: LiteralString,
        event_factory: EventFactoryT,
        output_factory: OutputFactoryT,
        echo_factory: EchoFactoryT,
    ) -> None:
        super().__init__(hook_type=AdapterLifeSpan, hook_tag=protocol)

        self.protocol = protocol
        self.in_srcs: set[InSourceT] = set()
        self.out_srcs: set[OutSourceT] = set()
        self.dispatcher: "Dispatcher"
        self._event_factory = event_factory
        self._output_factory = output_factory
        self._echo_factory = echo_factory

        self._inited = False
        self.__mark_repeatable_hooks__(
            AdapterLifeSpan.BEFORE_EVENT_HANDLE, AdapterLifeSpan.BEFORE_ACTION_EXEC
        )

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
        while True:
            try:
                packet = await src.input()
                event: Event = await self._event_factory.create(packet)
                EventOrigin.set_origin(event, EventOrigin(self, src))
                await self._hook_bus.emit(AdapterLifeSpan.BEFORE_EVENT_HANDLE, True, args=(event,))
                self.dispatcher.broadcast(event)
            except Exception as e:
                log_exc(
                    e,
                    msg=f"适配器 {self} 处理输入源 {src} 时发生异常",
                    obj={
                        "in_factory": self._event_factory,
                        "dispatcher": self.dispatcher,
                    }
                    | locals(),
                )

    @asynccontextmanager
    @final
    async def __wait_close_hook__(self) -> AsyncGenerator[None, None]:
        try:
            yield
        finally:
            await self._hook_bus.emit(AdapterLifeSpan.CLOSE, True)

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

                # 防止有些输入输出源在第一次启动失败后，又触发一次下面的启动
                in_src_set = cast(set[AbstractSource], self.in_srcs) - cast(
                    set[AbstractSource], self.out_srcs
                )
                in_src_ts = tuple(
                    create_task(stack.enter_async_context(src))
                    for src in in_src_set
                    if not src.opened()
                )
                if len(in_src_ts):
                    await asyncio.wait(in_src_ts)

                for src in self.in_srcs:
                    create_task(self.__adapter_input_loop__(src))

                await stack.enter_async_context(self.__wait_close_hook__())
                self._inited = True
                await self._hook_bus.emit(AdapterLifeSpan.STARTED)
                yield self

        finally:
            if self._inited:
                await self._hook_bus.emit(AdapterLifeSpan.STOPPED, True)

    @final
    def filter_out(
        self, filter: Callable[[OutSourceT], bool]
    ) -> _GeneratorContextManager[Callable[[OutSourceT], bool]]:
        """上下文管理器，提供由 `filter` 控制输出的输出上下文

        :param filter: 过滤函数，为 `True` 时允许该输出源输出
        """
        return _OUT_SRC_FILTER_CTX.unfold(filter)

    async def call_output(self, action: ActionT) -> ActionHandleGroup:
        """输出行为，返回 :class:`.ActionHandleGroup`

        适配器开发者的适配器子类可以重写此方法，以实现自定义功能

        但子类实现中必须调用原始方法： `super().call_output(...)`

        :param action: 行为
        :return: :class:`.ActionHandleGroup` 对象
        """
        osrcs: Iterable[OutSourceT]
        filter = _OUT_SRC_FILTER_CTX.try_get()
        cur_isrc: AbstractInSource | None

        if event := _FLOW_CTX.try_get_event():
            cur_isrc = EventOrigin.get_origin(event).in_src
        else:
            cur_isrc = None

        if filter is not None:
            osrcs = (osrc for osrc in self.out_srcs if filter(osrc))
        elif isinstance(cur_isrc, AbstractOutSource) and cur_isrc in self.out_srcs:
            osrcs = (cast(OutSourceT, cur_isrc),)
        else:
            osrcs = self.out_srcs if len(self.out_srcs) else ()

        await self._hook_bus.emit(AdapterLifeSpan.BEFORE_ACTION_EXEC, True, args=(action,))
        hs: tuple[ActionHandle, ...] = tuple(
            ActionHandle(action, osrc, self._output_factory, self._echo_factory) for osrc in osrcs
        )
        return ActionHandleGroup(*hs)

    @abstractmethod
    async def __send_text__(self, text: str) -> ActionHandleGroup:
        """输出文本

        抽象方法。所有适配器子类应该实现此方法

        :param text: 文本
        :return: :class:`.ActionHandleGroup` 对象
        """
        raise NotImplementedError

    async def __send_media__(
        self,
        name: str,
        raw: bytes | None = None,
        url: str | None = None,
        mimetype: str | None = None,
    ) -> ActionHandleGroup:
        """输出多媒体内容

        建议所有适配器子类重写此方法，否则回退到基类实现：仅使用 :func:`send_text` 输出相关提示信息

        :param name: 多媒体内容的名称
        :param raw: 多媒体内容的二进制内容
        :param url: 多媒体内容的网络地址（和 `raw` 参数二选一）
        :param mimetype: 多媒体内容的 mimetype，为空则根据 `name` 自动检测
        :return: :class:`.ActionHandleGroup` 对象
        """
        return await self.__send_text__(
            f"[melobot media: {name if url is None else name + ' at ' + url}]"
        )

    async def __send_image__(
        self,
        name: str,
        raw: bytes | None = None,
        url: str | None = None,
        mimetype: str | None = None,
    ) -> ActionHandleGroup:
        """输出图像内容

        建议所有适配器子类重写此方法，否则回退到基类实现：仅使用 :func:`send_text` 输出相关提示信息

        :param name: 图像内容的名称
        :param raw: 图像内容的二进制内容
        :param url: 图像内容的网络地址（和 `raw` 参数二选一）
        :param mimetype: 图像内容的 mimetype，为空则根据 `name` 自动检测
        :return: :class:`.ActionHandleGroup` 对象
        """
        return await self.__send_text__(
            f"[melobot image: {name if url is None else name + ' at ' + url}]"
        )

    async def __send_audio__(
        self,
        name: str,
        raw: bytes | None = None,
        url: str | None = None,
        mimetype: str | None = None,
    ) -> ActionHandleGroup:
        """输出音频内容

        建议所有适配器子类重写此方法，否则回退到基类实现：仅使用 :func:`send_text` 输出相关提示信息

        :param name: 音频内容的名称
        :param raw: 音频内容的二进制内容
        :param url: 音频内容的网络地址（和 `raw` 参数二选一）
        :param mimetype: 音频内容的 mimetype，为空则根据 `name` 自动检测
        :return: :class:`.ActionHandleGroup` 对象
        """
        return await self.__send_text__(
            f"[melobot audio: {name if url is None else name + ' at ' + url}]"
        )

    async def __send_voice__(
        self,
        name: str,
        raw: bytes | None = None,
        url: str | None = None,
        mimetype: str | None = None,
    ) -> ActionHandleGroup:
        """输出语音内容

        建议所有适配器子类重写此方法，否则回退到基类实现：仅使用 :func:`send_text` 输出相关提示信息

        :param name: 语音内容的名称
        :param raw: 语音内容的二进制内容
        :param url: 语音内容的网络地址（和 `raw` 参数二选一）
        :param mimetype: 语音内容的 mimetype，为空则根据 `name` 自动检测
        :return: :class:`.ActionHandleGroup` 对象
        """
        return await self.__send_text__(
            f"[melobot voice: {name if url is None else name + ' at ' + url}]"
        )

    async def __send_video__(
        self,
        name: str,
        raw: bytes | None = None,
        url: str | None = None,
        mimetype: str | None = None,
    ) -> ActionHandleGroup:
        """输出视频内容

        建议所有适配器子类重写此方法，否则回退到基类实现：仅使用 :func:`send_text` 输出相关提示信息

        :param name: 视频内容的名称
        :param raw: 视频内容的二进制内容
        :param url: 视频内容的网络地址（和 `raw` 参数二选一）
        :param mimetype: 视频内容的 mimetype，为空则根据 `name` 自动检测
        :return: :class:`.ActionHandleGroup` 对象
        """
        return await self.__send_text__(
            f"[melobot video: {name if url is None else name + ' at ' + url}]"
        )

    async def __send_file__(self, name: str, path: str | PathLike[str]) -> ActionHandleGroup:
        """输出文件

        建议所有适配器子类重写此方法，否则回退到基类实现：仅使用 :func:`send_text` 输出相关提示信息

        :param name: 文件名
        :param path: 文件路径
        :return: :class:`.ActionHandleGroup` 对象
        """
        return await self.__send_text__(f"[melobot file: {name} at {path}]")

    async def __send_refer__(
        self, event: Event, contents: Sequence[Content] | None = None
    ) -> ActionHandleGroup:
        """输出对过往事件的引用

        建议所有适配器子类重写此方法，否则回退到基类实现：仅使用 :func:`send_text` 输出相关提示信息

        :param event: 过往的事件对象
        :param contents: 附加的通用内容序列
        :return: :class:`.ActionHandleGroup` 对象
        """
        return await self.__send_text__(f"[melobot refer: {event.__class__.__name__}({event.id})]")

    async def __send_resource__(self, name: str, url: str) -> ActionHandleGroup:
        """输出网络资源

        建议所有适配器子类重写此方法，否则回退到基类实现：仅使用 :func:`send_text` 输出相关提示信息

        :param name: 网络资源名称
        :param url: 网络资源的 url
        :return: :class:`.ActionHandleGroup` 对象
        """
        return await self.__send_text__(f"[melobot resource: {name} at {url}]")


AdapterT = TypeVar("AdapterT", bound=Adapter)
