from __future__ import annotations

import asyncio
import contextvars
import os
import platform
from contextlib import AsyncExitStack, ExitStack, asynccontextmanager, contextmanager
from enum import Enum
from os import PathLike
from pathlib import Path
from random import random
from types import ModuleType
from weakref import WeakValueDictionary

from typing_extensions import (
    Any,
    AsyncGenerator,
    Callable,
    Generator,
    Iterable,
    Literal,
    LiteralString,
    NoReturn,
    overload,
)

from .._meta import MetaInfo
from .._run import AsyncRunner
from ..adapter.base import Adapter, AdapterT
from ..adapter.model import Event
from ..ctx import BotCtx
from ..exceptions import BotError
from ..handle.base import Flow
from ..io.base import AbstractInSource, AbstractIOSource, AbstractOutSource
from ..log.base import GenericLogger
from ..log.reflect import logger
from ..log.report import set_loop_exc_log
from ..mixin import HookMixin
from ..plugin.base import Plugin, PluginLifeSpan, PluginPlanner
from ..plugin.ipc import AsyncShare, IPCManager, SyncShare
from ..plugin.load import PluginLoader
from ..protocols.base import ProtocolStack
from ..typ.base import AsyncCallable, P, SyncOrAsyncCallable
from .dispatch import Dispatcher, wait_dispatched


class BotLifeSpan(Enum):
    """bot 生命周期阶段的枚举"""

    #: 所有插件加载之后
    LOADED = "l"
    #: bot 启动完成之后（此时所有适配器和源已经开始工作）
    STARTED = "sta"
    #: bot 重新启动完成之后
    RESTARTED = "r"
    #: bot 手动停止即将发生前（仅限 bot.close() 和 bot.restart() 发起的，信号处理不会触发此类型，出现异常可能不触发此类型）
    CLOSE = "c"
    #: bot 停止完成后（包含任何情况导致的停止，请在这里处理清理工作）
    STOPPED = "sto"

    RELOADED: Literal["r"]


# 兼容旧版本
BotLifeSpan.RELOADED = BotLifeSpan.RESTARTED  # type: ignore[assignment]

_BOT_CTX = BotCtx()
_LUCKY_VALUE = random()


def _start_log() -> None:
    for row in MetaInfo.logo.split("\n"):
        logger.info(f"{row}")
    logger.info("")
    logger.info(f"版本：{MetaInfo.ver}")
    logger.info(f"系统：{platform.system()} {platform.release()} {platform.machine()}")
    logger.info(f"环境：{platform.python_implementation()} {platform.python_version()}")
    if _LUCKY_VALUE >= 0.999:
        logger.info("彩蛋：恭喜你触发了这个彩蛋，本次运行幸运值 +65535 ✨")

    logger.info("=" * 40)


def _end_log() -> None:
    if _LUCKY_VALUE >= 0.999:
        logger.info('melobot: "我们弹下的每段旋律，终将在某时回归 🎵"')


class Bot(HookMixin[BotLifeSpan]):
    """bot 类

    :ivar str name: bot 对象的名称
    :ivar GenericLogger logger: bot 对象使用的日志器
    """

    __instances__: WeakValueDictionary[str, Bot] = WeakValueDictionary()

    def __new__(cls, name: str = "melobot", /, *args: Any, **kwargs: Any) -> Bot:
        if name in Bot.__instances__:
            raise BotError(f"命名为 {name} 的 bot 实例已存在，请改名避免冲突")
        obj = super().__new__(cls)
        Bot.__instances__[name] = obj
        return obj

    def __init__(self, name: str = "melobot", /, logger: GenericLogger | None = None) -> None:
        """
        初始化 bot

        :param name: bot 名称
        :param logger:
            bot 使用的日志器，符合 :class:`.GenericLogger` 的接口即可。
            可使用 melobot 内置的 :class:`.Logger`，或经过 :func:`.logger_patch` 修补的日志器
        """
        super().__init__(hook_type=BotLifeSpan, hook_tag=name)

        self.name = name
        self.logger = logger

        self.adapters: dict[str, Adapter] = {}
        self.ipc_manager = IPCManager()

        self._runner = AsyncRunner()
        self._in_srcs: dict[str, set[AbstractInSource]] = {}
        self._out_srcs: dict[str, set[AbstractOutSource]] = {}
        self._loader = PluginLoader()
        self._plugins: dict[str, Plugin] = {}
        self._dispatcher = Dispatcher()
        self._inited = False
        self._running = False
        self._closed = False

        self.__life: asyncio.Task | None = None
        self.__terminated = False
        self.__happy_end = asyncio.Event()

    def __repr__(self) -> str:
        return f'Bot(name="{self.name}")'

    @contextmanager
    def _common_sync_ctx(self) -> Generator[ExitStack, None, None]:
        with ExitStack() as stack:
            stack.enter_context(_BOT_CTX.unfold(self))
            yield stack

    @asynccontextmanager
    async def _common_async_ctx(self) -> AsyncGenerator[AsyncExitStack, None]:
        async with AsyncExitStack() as stack:
            stack.enter_context(_BOT_CTX.unfold(self))
            yield stack

    def add_input(self, src: AbstractInSource) -> Bot:
        """绑定输入源

        :param src: 输入源
        :return: bot 对象，因此支持链式调用
        """
        if self._inited:
            raise BotError(f"{self} 已不在初始化期，无法再绑定输入源")

        self._in_srcs.setdefault(src.protocol, set()).add(src)
        return self

    def add_output(self, src: AbstractOutSource) -> Bot:
        """绑定输出源

        :param src: 输出源
        :return: bot 对象，因此支持链式调用
        """
        if self._inited:
            raise BotError(f"{self} 已不在初始化期，无法再绑定输出源")

        self._out_srcs.setdefault(src.protocol, set()).add(src)
        return self

    def add_io(self, src: AbstractIOSource) -> Bot:
        """绑定输入输出源

        :param src: 输入输出源
        :return: bot 对象，因此支持链式调用
        """
        self.add_input(src)
        self.add_output(src)
        return self

    def add_adapter(self, adapter: Adapter) -> Bot:
        """绑定适配器

        :param adapter: 适配器对象
        :return: bot 对象，因此支持链式调用
        """
        if self._inited:
            raise BotError(f"{self} 已不在初始化期，无法再绑定适配器")
        if adapter.protocol in self.adapters:
            raise BotError(f"已存在协议 {adapter.protocol} 的适配器，同协议的适配器不能再绑定")

        self.adapters[adapter.protocol] = adapter
        return self

    def add_protocol(self, pstack: ProtocolStack | type[ProtocolStack]) -> Bot:
        """绑定完整的协议栈，这包含了一组协同工作的输入源、输出源和适配器

        :param pstack: 协议栈对象或协议栈类
        :return: bot 对象，因此支持链式调用
        """
        if isinstance(pstack, type):
            pstack = pstack()
        insrcs, outsrcs, adapter = pstack.inputs, pstack.outputs, pstack.adapter
        self.add_adapter(adapter)
        for isrc in insrcs:
            self.add_input(isrc)
        for osrc in outsrcs:
            self.add_output(osrc)
        return self

    def _core_init(self) -> None:
        if self._inited:
            return
        _start_log()

        for protocol, srcs in self._in_srcs.items():
            for isrc in srcs:
                adapter = self.adapters.get(protocol)
                if adapter is not None:
                    adapter.in_srcs.add(isrc)
                else:
                    logger.warning(f"输入源 {isrc.__class__.__name__} 没有对应的适配器")

        for protocol, outsrcs in self._out_srcs.items():
            for osrc in outsrcs:
                adapter = self.adapters.get(protocol)
                if adapter is not None:
                    adapter.out_srcs.add(osrc)
                else:
                    logger.warning(f"输出源 {osrc.__class__.__name__} 没有对应的适配器")

        for adapter in self.adapters.values():
            if not len(adapter.in_srcs) and not len(adapter.out_srcs):
                logger.warning(f"适配器 {adapter.__class__.__name__} 没有对应的输入源或输出源")
            adapter.dispatcher = self._dispatcher

        self._inited = True
        logger.debug("bot 核心组件初始化完成")

    def load_plugin(
        self,
        plugin: ModuleType | str | PathLike[str] | PluginPlanner,
        load_depth: int = 1,
    ) -> Bot:
        """加载插件，非线程安全

        :param plugin: 可以被加载为插件的对象（插件目录对应的模块，插件的目录路径，可直接 import 包名称，插件管理器对象）
        :param load_depth:
            插件加载时的相对引用深度，默认值 1 只支持向上引用到插件目录一级。
            增加为 2 可以引用到插件目录的父目录一级，依此类推。
            此参数只在 `plugin` 参数为插件的目录路径时有效。
        :return: bot 对象，因此支持链式调用
        """
        self._core_init()
        with self._common_sync_ctx():
            p, is_loaded = self._loader.load(plugin, load_depth)
            if is_loaded:
                return self

            self._plugins[p.name] = p
            for share in p.shares:
                self.ipc_manager.add(p.name, share)
            for func in p.funcs:
                self.ipc_manager.add_func(p.name, func)
            logger.info(f"成功加载插件：{p.name}")

            if self._hook_bus.get_evoke_time(BotLifeSpan.STARTED) != -1:
                asyncio.create_task(
                    p.hook_bus.emit(
                        PluginLifeSpan.INITED,
                        callback=lambda _, p=p: self._dispatcher.add(*p.init_flows),
                    )
                )
            return self

    def load_plugins(
        self,
        plugins: Iterable[ModuleType | str | PathLike[str] | PluginPlanner],
        load_depth: int = 1,
    ) -> None:
        """与 :func:`load_plugin` 行为类似，但是参数变为可迭代对象

        此方法同样不是线程安全的

        :param plugins: 可迭代对象，包含：可以被加载为插件的对象（插件目录对应的模块，插件的目录路径，插件对象）
        :param load_depth: 参见 :func:`load_plugin` 同名参数
        """
        for p in plugins:
            self.load_plugin(p, load_depth)

    def load_plugins_dir(self, pdir: str | PathLike[str], load_depth: int = 1) -> None:
        """与 :func:`load_plugin` 行为类似，但是参数变为插件目录的父目录，本方法可以加载单个目录下的多个插件

        此方法同样不是线程安全的

        :param pdir: 插件所在父目录的路径
        :param load_depth: 参见 :func:`load_plugin` 同名参数
        """
        parent_dir = Path(pdir).resolve()
        plugin_dirs: list[Path] = []

        for dirname in os.listdir(parent_dir):
            path = Path(parent_dir).joinpath(dirname)
            if path.is_dir() and path.parts[-1] != "__pycache__":
                plugin_dirs.append(path)

        self.load_plugins(plugin_dirs, load_depth)

    def load_plugins_dirs(self, pdirs: Iterable[str | PathLike[str]], load_depth: int = 1) -> None:
        """与 :func:`load_plugins_dir` 行为类似，但是参数变为可迭代对象，每个元素为包含插件目录的父目录。
        本方法可以加载多个目录下的多个插件

        此方法同样不是线程安全的

        :param pdirs: 可迭代对象，包含：插件所在父目录的路径
        :param load_depth: 参见 :func:`load_plugin` 同名参数
        """
        for pdir in pdirs:
            self.load_plugins_dir(pdir, load_depth)

    async def _run(self) -> None:
        if self._closed:
            raise BotError(f"{self} 已停止运行，无法再次运行")
        self._core_init()
        if self._running:
            raise BotError(f"{self} 已在运行中，不能再次启动运行")
        self._running = True
        self.__life = asyncio.current_task()

        logger.debug(f"当前事件循环类型：{type(asyncio.get_running_loop())}")
        try:
            async with self._common_async_ctx() as stack:
                self._dispatcher.set_channel_ctx(contextvars.copy_context())

                await self._hook_bus.emit(BotLifeSpan.LOADED)
                if self._runner.is_from_restart():
                    await self._hook_bus.emit(BotLifeSpan.RESTARTED)

                for p in self._plugins.values():
                    await p.hook_bus.emit(
                        PluginLifeSpan.INITED,
                        callback=lambda _, p=p: self._dispatcher.add(*p.init_flows),
                    )

                ts = tuple(
                    asyncio.create_task(stack.enter_async_context(adapter.__adapter_launch__()))
                    for adapter in self.adapters.values()
                )
                if len(ts):
                    await asyncio.wait(ts)

                await self._hook_bus.emit(BotLifeSpan.STARTED)
                await self.__happy_end.wait()

        finally:
            async with self._common_async_ctx() as stack:
                await self._hook_bus.emit(BotLifeSpan.STOPPED, True)
                logger.info(f"{self} 已安全停止运行")
                self._running = False

    def run(
        self,
        debug: bool = False,
        strict_log: bool = False,
        use_exc_handler: bool = True,
        loop_factory: Callable[[], asyncio.AbstractEventLoop] | None = None,
        eager_task: bool = True,
    ) -> None:
        """运行 bot 的阻塞方法（将在内部创建事件循环），这适用于只运行单一 bot 的情况

        :param debug: 是否启用 :py:mod:`asyncio` 的调试模式，但是这不会更改 :py:mod:`asyncio` 日志器的日志等级
        :param strict_log: 是否启用严格日志，启用后事件循环中的未捕获异常都会输出错误日志，否则未捕获异常将只输出调试日志
        :param use_exc_handler:
            是否使用内置的事件循环异常处理器来处理未捕获异常，为 False 时 `strict_log` 参数无效。
            设置为 True 时，未捕获异常会被记录到日志中。并在运行结束后重置为调用前的异常处理器
        :param loop_factory:
            使用此参数提供事件循环工厂。
            Python 3.14 版本开始弃用事件循环策略，替代方案为事件循环工厂。
            当然在 < 3.16 的版本，你依然可以不提供此参数，继续使用事件循环策略设置事件循环类型
        :param eager_task: 是否启用主动任务模式（Python 3.12+ 可用），启用后任务会在创建时立即执行协程直到第一个 await 表达式
        """
        logger.info("当前模式：事件循环由内部创建")
        set_loop_exc_log(strict_log)
        self._runner.run(
            self._run(), self._terminator, debug, use_exc_handler, loop_factory, eager_task
        )
        _end_log()

    async def run_async(
        self,
        strict_log: bool = False,
        use_exc_handler: bool = True,
        reserved_tasks: set[asyncio.Task] | None = None,
        pre_loop_sig_handlers: list[tuple[int, Callable[..., object]]] | None = None,
        shutdown_asyncgens: bool = False,
        shutdown_default_executor: bool = False,
    ) -> None:
        """运行 bot 的异步方法（将在已有的事件循环中运行），这适用于只运行单一 bot 的情况

        我们仅推荐在测试环境中使用此方法，因为部分测试框架的异步测试会先运行一个事件循环（如 pytest-asyncio）。
        在复杂的生产环境中，无法 100% 保证运行前后事件循环的状态不被破坏

        :param strict_log: 是否启用严格日志，启用后事件循环中的未捕获异常都会输出错误日志，否则未捕获异常将只输出调试日志
        :param use_exc_handler:
            是否使用内置的事件循环异常处理器来处理未捕获异常，为 False 时 `strict_log` 参数无效。
            设置为 True 时，未捕获异常会被记录到日志中。此方法运行结束后重置为调用前的异常处理器
        :param reserved_tasks:
            bot 运行结束时，会取消事件循环中除此方法调用栈上的其他任务，此参数提供不需要取消的任务的集合。
            这一般适用于在调用此方法时，已存在其他非本栈上的异步任务的情况
        :param pre_loop_sig_handlers:
            bot 运行时会尝试覆盖原有的信号处理函数，对于 Windows 平台，在运行结束后自动重置为调用前的信号处理函数。
            但对于其他平台，内部使用 :py:mod:`~asyncio.AbstractEventLoop.add_signal_handler` 方法添加信号处理函数，
            无法获取到先前的信号处理函数。如果需要重置，请使用此参数提供调用前的信号处理函数列表
        :param shutdown_asyncgens: 运行结束后是否关闭事件循环中所有异步生成器
        :param shutdown_default_executor: 运行结束后是否关闭事件循环的默认执行器
        """
        logger.info("当前模式：事件循环由外部创建")
        set_loop_exc_log(strict_log)
        await self._runner.run_async(
            self._run(),
            self._terminator,
            reserved_tasks,
            use_exc_handler,
            pre_loop_sig_handlers,
            shutdown_asyncgens,
            shutdown_default_executor,
        )
        _end_log()

    async def close(self) -> None:
        """停止并关闭当前 bot"""
        if not self._running:
            raise BotError(f"{self} 未在运行中，不能停止运行")

        await self._hook_bus.emit(BotLifeSpan.CLOSE, True)
        self.__happy_end.set()

    def is_restartable(self) -> bool:
        """判断当前 bot 是否可以重启

        :return: 是否可以重启
        """
        if len(self.__class__.__instances__) > 1:
            return False
        return self._runner.is_restartable()

    async def restart(self) -> NoReturn:
        """重启当前 bot，需要通过模块运行模式启动 bot 主脚本：

        .. code:: shell

            python3 -m melobot run xxx.py

        另外请注意，重启功能只在启动了一个 bot 时生效，多个 bot 同时运行时无法重启
        """
        if not self._runner.is_restartable():
            raise BotError("使用重启功能，需要用以下命令运行 bot：python -m melobot run xxx.py")

        await self.close()
        self._runner.restart()

    def _terminator(self) -> None:
        # signal handle 及手动调用保持幂等性
        if self.__terminated or self._closed or not self._running:
            return
        if self.get_hook_evoke_time(BotLifeSpan.STARTED) != -1:
            self.__happy_end.set()
            self.__terminated = True
            return
        if self.__life is None:
            return
        self.__life.cancel()
        self.__terminated = True

    @overload
    def get_adapter(self, type: type[AdapterT], filter: None = None) -> AdapterT | None: ...

    @overload
    def get_adapter(self, type: LiteralString, filter: None = None) -> Adapter | None: ...

    @overload
    def get_adapter(
        self, type: None = None, filter: Callable[[Adapter], bool] | None = None
    ) -> Adapter | None: ...

    def get_adapter(
        self,
        type: LiteralString | type[Adapter] | None = None,
        filter: Callable[[Adapter], bool] | None = None,
    ) -> Adapter | None:
        """获取 bot 所绑定的适配器

        :param type: 适配器的类型（可传入协议字符串或适配器类型），为空时才使用 `filter` 参数
        :param filter: 过滤函数，返回 `True` 则表明需要该适配器。为空则不使用
        :return: 适配器或空
        """
        if type is not None:
            if isinstance(type, str):
                return self.adapters.get(type)

            for a in self.adapters.values():
                if isinstance(a, type):
                    return a
            return None

        if filter is not None:
            for adapter in self.adapters.values():
                if filter(adapter):
                    return adapter

        return None

    def get_adapters(self, filter: Callable[[Adapter], bool] | None = None) -> set[Adapter]:
        """获取一组适配器

        :param filter: 参见 :func:`get_adapter` 同名参数。但此处为空时直接获取所有适配器
        :return: 适配器的集合
        """
        if filter is None:
            return set(self.adapters.values())
        return set(adapter for adapter in self.adapters.values() if filter(adapter))

    def get_plugins(self) -> list[str]:
        """获取所有绑定的插件的名称

        :return: 所绑定的插件的名称列表
        """
        return list(self._plugins.keys())

    def get_share(self, plugin: str, share: str) -> SyncShare | AsyncShare:
        """获取绑定的插件中的共享对象

        :param plugin: 插件名称
        :param share: 共享对象的标识
        :return: 共享对象
        """
        return self.ipc_manager.get(plugin, share)

    def add_flows(self, *flows: Flow) -> None:
        """添加处理流，非线程安全

        :param flows: 流对象
        """
        self._dispatcher.add(*flows)

    async def wait_finish(self, event: Event) -> None:
        """等待事件被所有处理流处理完成

        :param event: 事件对象
        """
        await wait_dispatched(event, self)

    @property
    def on_loaded(
        self,
    ) -> Callable[[SyncOrAsyncCallable[P, None]], AsyncCallable[P, None]]:
        """给 bot 注册 :obj:`.BotLifeSpan.LOADED` 阶段 hook 的装饰器"""
        return self.on(BotLifeSpan.LOADED)

    @property
    def on_reloaded(
        self,
    ) -> Callable[[SyncOrAsyncCallable[P, None]], AsyncCallable[P, None]]:
        """给 bot 注册 :obj:`.BotLifeSpan.RESTARTED` 阶段 hook 的装饰器"""
        return self.on(BotLifeSpan.RESTARTED)

    @property
    def on_restarted(
        self,
    ) -> Callable[[SyncOrAsyncCallable[P, None]], AsyncCallable[P, None]]:
        """给 bot 注册 :obj:`.BotLifeSpan.RESTARTED` 阶段 hook 的装饰器"""
        return self.on(BotLifeSpan.RESTARTED)

    @property
    def on_started(
        self,
    ) -> Callable[[SyncOrAsyncCallable[P, None]], AsyncCallable[P, None]]:
        """给 bot 注册 :obj:`.BotLifeSpan.STARTED` 阶段 hook 的装饰器"""
        return self.on(BotLifeSpan.STARTED)

    @property
    def on_close(
        self,
    ) -> Callable[[SyncOrAsyncCallable[P, None]], AsyncCallable[P, None]]:
        """给 bot 注册 :obj:`.BotLifeSpan.CLOSE` 阶段 hook 的装饰器"""
        return self.on(BotLifeSpan.CLOSE)

    @property
    def on_stopped(
        self,
    ) -> Callable[[SyncOrAsyncCallable[P, None]], AsyncCallable[P, None]]:
        """给 bot 注册 :obj:`.BotLifeSpan.STOPPED` 阶段 hook 的装饰器"""
        return self.on(BotLifeSpan.STOPPED)
