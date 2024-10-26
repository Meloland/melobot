from __future__ import annotations

import asyncio
import asyncio.tasks
import importlib
import os
import platform
import sys
from contextlib import AsyncExitStack, ExitStack, asynccontextmanager, contextmanager
from enum import Enum
from os import PathLike
from pathlib import Path
from types import ModuleType
from typing import Any, AsyncGenerator, Callable, Coroutine, Generator, Iterable

from typing_extensions import LiteralString

from .._hook import HookBus
from .._meta import MetaInfo
from ..adapter.base import Adapter
from ..ctx import BotCtx, LoggerCtx
from ..exceptions import BotError
from ..io.base import AbstractInSource, AbstractIOSource, AbstractOutSource
from ..log.base import GenericLogger, Logger, NullLogger
from ..plugin.base import Plugin
from ..plugin.ipc import AsyncShare, IPCManager, SyncShare
from ..plugin.load import PluginLoader
from ..protocols.base import ProtocolStack
from ..typ import AsyncCallable, P
from .dispatch import Dispatcher


class BotLifeSpan(Enum):
    """bot 生命周期阶段的枚举"""

    LOADED = "l"
    RELOADED = "r"
    STARTED = "sta"
    CLOSE = "c"
    STOPPED = "sto"


class BotExitSignal(Enum):
    NORMAL_STOP = 0
    ERROR = 1
    RESTART = 2


MELO_PKG_RUNTIME = "MELOBOT_PKG_RUNTIME"
MELO_LAST_EXIT_SIGNAL = "MELO_LAST_EXIT_SIGNAL"
_BOT_CTX = BotCtx()
_LOGGER_CTX = LoggerCtx()


def _start_log(logger: GenericLogger) -> None:
    for row in MetaInfo.logo.split("\n"):
        logger.info(f"{row}")
    logger.info("")
    logger.info(f"版本：{MetaInfo.ver}")
    logger.info(f"系统：{platform.system()} {platform.machine()} {platform.release()}")
    logger.info(f"环境：{platform.python_implementation()} {platform.python_version()}")
    logger.info("=" * 40)


class Bot:
    """bot 类

    :ivar str name: bot 对象的名称
    :ivar GenericLogger logger: bot 对象使用的日志器
    """

    __instances__: dict[str, Bot] = {}

    def __new__(cls, name: str = "melobot", /, *args: Any, **kwargs: Any) -> Bot:
        if name in Bot.__instances__:
            raise BotError(f"命名为 {name} 的 bot 实例已存在，请改名避免冲突")
        obj = super().__new__(cls)
        Bot.__instances__[name] = obj
        return obj

    def __init__(
        self,
        name: str = "melobot",
        /,
        logger: GenericLogger | None = None,
        enable_log: bool = True,
    ) -> None:
        """
        初始化 bot

        :param name: bot 名称
        :param logger:
            bot 使用的日志器，符合 :class:`.GenericLogger` 的接口即可。
            可使用 melobot 内置的 :class:`.Logger`，或经过 :func:`.logger_patch` 修补的日志器
        :param enable_log: 是否启用日志功能
        """
        self.name = name
        self.logger: GenericLogger
        if not enable_log:
            self.logger = NullLogger()
        elif logger is None:
            self.logger = Logger()
        else:
            self.logger = logger

        self.adapters: dict[str, Adapter] = {}
        self.ipc_manager = IPCManager()

        self._in_srcs: dict[str, list[AbstractInSource]] = {}
        self._out_srcs: dict[str, list[AbstractOutSource]] = {}
        self._loader = PluginLoader()
        self._plugins: dict[str, Plugin] = {}
        self._life_bus = HookBus[BotLifeSpan](BotLifeSpan)
        self._dispatcher = Dispatcher()
        self._tasks: list[asyncio.Task] = []

        self._inited = False
        self._running = False
        self._rip_signal = asyncio.Event()

    def __repr__(self) -> str:
        return f'Bot(name="{self.name}")'

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        """获得当前 bot 运行时的事件循环对象"""
        return asyncio.get_running_loop()

    @contextmanager
    def _sync_common_ctx(self) -> Generator[ExitStack, None, None]:
        with ExitStack() as stack:
            stack.enter_context(_BOT_CTX.in_ctx(self))
            stack.enter_context(_LOGGER_CTX.in_ctx(self.logger))
            yield stack

    @asynccontextmanager
    async def _async_common_ctx(self) -> AsyncGenerator[AsyncExitStack, None]:
        async with AsyncExitStack() as stack:
            stack.enter_context(_BOT_CTX.in_ctx(self))
            stack.enter_context(_LOGGER_CTX.in_ctx(self.logger))
            yield stack

    def add_input(self, src: AbstractInSource) -> Bot:
        """绑定输入源

        :param src: 输入源
        :return: bot 对象，因此支持链式调用
        """
        if self._inited:
            raise BotError(f"{self} 已不在初始化期，无法再绑定输入源")

        self._in_srcs.setdefault(src.protocol, []).append(src)
        return self

    def add_output(self, src: AbstractOutSource) -> Bot:
        """绑定输出源

        :param src: 输出源
        :return: bot 对象，因此支持链式调用
        """
        if self._inited:
            raise BotError(f"{self} 已不在初始化期，无法再绑定输出源")

        self._out_srcs.setdefault(src.protocol, []).append(src)
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
            raise BotError(
                f"已存在协议 {adapter.protocol} 的适配器，同协议的适配器不能再绑定"
            )

        self.adapters[adapter.protocol] = adapter
        return self

    def add_protocol(self, pstack: ProtocolStack) -> Bot:
        """绑定完整的协议栈，这包含了一组协同工作的输入源、输出源和适配器

        :param pstack: 协议栈对象
        :return: bot 对象，因此支持链式调用
        """
        insrcs, outsrcs, adapter = pstack.inputs, pstack.outputs, pstack.adapter
        self.add_adapter(adapter)
        for isrc in insrcs:
            self.add_input(isrc)
        for osrc in outsrcs:
            self.add_output(osrc)
        return self

    def _run_init(self) -> None:
        _start_log(self.logger)

        for protocol, srcs in self._in_srcs.items():
            for isrc in srcs:
                adapter = self.adapters.get(protocol)
                if adapter is not None:
                    adapter.in_srcs.append(isrc)
                else:
                    self.logger.warning(
                        f"输入源 {isrc.__class__.__name__} 没有对应的适配器"
                    )

        for protocol, outsrcs in self._out_srcs.items():
            for osrc in outsrcs:
                adapter = self.adapters.get(protocol)
                if adapter is not None:
                    adapter.out_srcs.append(osrc)
                else:
                    self.logger.warning(
                        f"输出源 {osrc.__class__.__name__} 没有对应的适配器"
                    )

        for adapter in self.adapters.values():
            if not len(adapter.in_srcs) and not len(adapter.out_srcs):
                self.logger.warning(
                    f"适配器 {adapter.__class__.__name__} 没有对应的输入源或输出源"
                )
            adapter.dispatcher = self._dispatcher

        self._inited = True
        self.logger.debug("bot 初始化完成，各核心组件已初始化")
        self.logger.debug(f"当前异步事件循环策略：{asyncio.get_event_loop_policy()}")

    def load_plugin(
        self, plugin: ModuleType | str | PathLike[str] | Plugin, load_depth: int = 1
    ) -> Bot:
        """加载插件

        :param plugin: 可以被加载为插件的对象（插件目录对应的模块，插件的目录路径，插件对象）
        :param load_depth:
            插件加载时的相对引用深度，默认值 1 只支持向上引用到插件目录一级。
            增加为 2 可以引用到插件目录的父目录一级，依此类推。
            此参数一般只适用于 `plugin` 参数为插件的目录路径的情况。
        :return: bot 对象，因此支持链式调用
        """
        if not self._inited:
            self._run_init()

        with self._sync_common_ctx():
            if not isinstance(plugin, Plugin):
                if isinstance(plugin, ModuleType):
                    p_name = plugin.__name__
                else:
                    p_name = Path(plugin).resolve().parts[-1]
                if p_name in self._plugins:
                    raise BotError(
                        f"尝试加载的插件 {p_name} 与其他已加载的 melobot 插件重名，请修改名称（修改插件目录名）"
                    )

            p = self._loader.load(plugin, load_depth)
            self._plugins[p.name] = p
            self._dispatcher.internal_add(*p.handlers)
            for share in p.shares:
                self.ipc_manager.add(p.name, share)
            for func in p.funcs:
                self.ipc_manager.add_func(p.name, func)
            self.logger.info(f"成功加载插件：{p.name}")

            return self

    def load_plugins(
        self,
        plugins: Iterable[ModuleType | str | PathLike[str] | Plugin],
        load_depth: int = 1,
    ) -> None:
        """与 :func:`load_plugin` 行为类似，但是参数变为可迭代对象

        :param plugins: 可迭代对象，包含：可以被加载为插件的对象（插件目录对应的模块，插件的目录路径，插件对象）
        :param load_depth: 参见 :func:`load_plugin` 同名参数
        """
        for p in plugins:
            self.load_plugin(p, load_depth)

    def load_plugins_dir(self, pdir: str | PathLike[str], load_depth: int = 1) -> None:
        """与 :func:`load_plugin` 行为类似，但是参数变为插件目录的父目录，本方法可以加载单个目录下的多个插件

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

    def load_plugins_dirs(
        self, pdirs: Iterable[str | PathLike[str]], load_depth: int = 1
    ) -> None:
        """与 :func:`load_plugins_dir` 行为类似，但是参数变为可迭代对象，每个元素为包含插件目录的父目录。
        本方法可以加载多个目录下的多个插件

        :param pdirs: 可迭代对象，包含：插件所在父目录的路径
        :param load_depth: 参见 :func:`load_plugin` 同名参数
        """
        for pdir in pdirs:
            self.load_plugins_dir(pdir, load_depth)

    def load_site_plugins(self, *site_plugins: str) -> None:
        """加载从站点上（例如 pip）安装的第三方插件

        :param site_plugins: 要加载的第三方插件的名称，例如 "melobot_plugin_example"
        """
        for pname in site_plugins:
            pmod = importlib.import_module(pname)
            self.load_plugin(pmod)

    async def core_run(self) -> None:
        """运行 bot 的方法，可以在异步事件循环中自由地使用

        若使用此方法，则需要自行管理异步事件循环
        """
        if not self._inited:
            self._run_init()

        if self._running:
            raise BotError(f"{self} 已在运行中，不能再次启动运行")
        self._running = True

        try:
            async with self._async_common_ctx() as stack:
                if (
                    MELO_LAST_EXIT_SIGNAL in os.environ
                    and int(os.environ[MELO_LAST_EXIT_SIGNAL])
                    == BotExitSignal.RESTART.value
                ):
                    await self._life_bus.emit(BotLifeSpan.RELOADED)
                else:
                    await self._life_bus.emit(BotLifeSpan.LOADED)

                timed_task = asyncio.create_task(self._dispatcher.timed_gc())
                self._tasks.append(timed_task)
                ts = tuple(
                    asyncio.create_task(
                        stack.enter_async_context(adapter.__adapter_launch__())
                    )
                    for adapter in self.adapters.values()
                )
                if len(ts):
                    await asyncio.wait(ts)

                await self._life_bus.emit(BotLifeSpan.STARTED)
                await self._rip_signal.wait()

        finally:
            async with self._async_common_ctx() as stack:
                for t in self._tasks:
                    t.cancel()
                await self._life_bus.emit(BotLifeSpan.STOPPED, wait=True)
                self.logger.info(f"{self} 已停止运行")
                self._running = False

    def run(self, debug: bool = False) -> None:
        """安全地运行 bot 的阻塞方法，这适用于只运行单一 bot 的情况

        :param debug: 是否启用 :py:mod:`asyncio` 的调试模式，但是这不会更改 :py:mod:`asyncio` 日志器的日志等级
        """
        _safe_run(self.core_run(), debug)

    @classmethod
    def start(cls, *bots: Bot, debug: bool = False) -> None:
        """安全地同时运行多个 bot 的阻塞方法

        :param bots: 要运行的 bot 对象
        :param debug: 参见 :func:`run` 同名参数
        """

        async def bots_run() -> None:
            tasks = []
            for bot in bots:
                tasks.append(asyncio.create_task(bot.core_run()))
            try:
                await asyncio.wait(tasks)
            except asyncio.CancelledError:
                pass

        _safe_run(bots_run(), debug)

    async def close(self) -> None:
        """停止并关闭当前 bot"""
        if not self._running:
            raise BotError(f"{self} 未在运行中，不能停止运行")

        await self._life_bus.emit(BotLifeSpan.CLOSE, wait=True)
        self._rip_signal.set()

    async def restart(self) -> None:
        """重启当前 bot，需要通过模块运行模式启动 bot 主脚本：

        .. code:: shell

            python3 -m melobot run [*.py]
        """
        if MELO_PKG_RUNTIME not in os.environ:
            raise BotError(
                "启用重启功能，需要用以下命令运行 bot：python -m melobot run [*.py]"
            )

        await self.close()
        sys.exit(BotExitSignal.RESTART.value)

    def get_adapter(
        self,
        protocol: LiteralString | None = None,
        filter: Callable[[Adapter], bool] | None = None,
    ) -> Adapter | None:
        """获取 bot 所绑定的适配器

        :param protocol: 适配器的协议，为空时才使用 `filter` 参数
        :param filter: 过滤函数，返回 `True` 则表明需要该适配器。为空则不使用
        :return: 适配器或空
        """
        if protocol:
            return self.adapters.get(protocol)
        if filter:
            for adapter in self.adapters.values():
                if filter(adapter):
                    return adapter
            return None
        raise BotError("protocol 或 filter 不能同时为空")

    def get_adapters(self, filter: Callable[[Adapter], bool]) -> set[Adapter]:
        """获取一组适配器

        :param filter: 参见 :func:`get_adapter` 同名参数
        :return: 适配器的集合
        """
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

    def on(
        self, *periods: BotLifeSpan
    ) -> Callable[[AsyncCallable[P, None]], AsyncCallable[P, None]]:
        """生成给 bot 注册生命周期回调的装饰器

        :param periods: 要绑定的生命周期阶段
        :return: 装饰器
        """

        def wrapped(func: AsyncCallable[P, None]) -> AsyncCallable[P, None]:
            for type in periods:
                self._life_bus.register(type, func)
            return func

        return wrapped

    @property
    def on_loaded(self) -> Callable[[AsyncCallable[P, None]], AsyncCallable[P, None]]:
        """给 bot 注册 loaded 生命周期回调的装饰器"""
        return self.on(BotLifeSpan.LOADED)

    @property
    def on_reloaded(self) -> Callable[[AsyncCallable[P, None]], AsyncCallable[P, None]]:
        """给 bot 注册 reloaded 生命周期回调的装饰器"""
        return self.on(BotLifeSpan.RELOADED)

    @property
    def on_started(self) -> Callable[[AsyncCallable[P, None]], AsyncCallable[P, None]]:
        """给 bot 注册 started 生命周期回调的装饰器"""
        return self.on(BotLifeSpan.STARTED)

    @property
    def on_close(self) -> Callable[[AsyncCallable[P, None]], AsyncCallable[P, None]]:
        """给 bot 注册 close 生命周期回调的装饰器"""
        return self.on(BotLifeSpan.CLOSE)

    @property
    def on_stopped(self) -> Callable[[AsyncCallable[P, None]], AsyncCallable[P, None]]:
        """给 bot 注册 stopped 生命周期回调的装饰器"""
        return self.on(BotLifeSpan.STOPPED)


def _safe_run(main: Coroutine[Any, Any, None], debug: bool) -> None:
    try:
        loop = asyncio.get_event_loop()
        asyncio.get_event_loop_policy().set_event_loop(loop)
        if debug is not None:
            loop.set_debug(debug)
        loop.run_until_complete(main)

    except KeyboardInterrupt:
        pass
    except asyncio.CancelledError:
        pass

    finally:
        try:
            _cancel_all_tasks(loop)
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.run_until_complete(loop.shutdown_default_executor())
        finally:
            asyncio.get_event_loop_policy().set_event_loop(None)
            loop.close()


def _cancel_all_tasks(loop: asyncio.AbstractEventLoop) -> None:
    to_cancel = asyncio.tasks.all_tasks(loop)
    if not to_cancel:
        return
    for task in to_cancel:
        task.cancel()
    loop.run_until_complete(asyncio.tasks.gather(*to_cancel, return_exceptions=True))

    for task in to_cancel:
        if task.cancelled():
            continue
        if task.exception() is not None:
            loop.call_exception_handler(
                {
                    "message": "unhandled exception during "
                    + f"{_safe_run.__qualname__}() shutdown",
                    "exception": task.exception(),
                    "task": task,
                }
            )
