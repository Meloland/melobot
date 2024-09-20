from __future__ import annotations

import asyncio
import asyncio.tasks
import os
import sys
from contextlib import AsyncExitStack, ExitStack, asynccontextmanager, contextmanager
from enum import Enum
from os import PathLike
from pathlib import Path
from types import ModuleType
from typing import Any, AsyncGenerator, Callable, Coroutine, Generator, Iterable

from typing_extensions import LiteralString

from .._hook import HookBus
from ..adapter.base import Adapter
from ..ctx import BotCtx, LoggerCtx
from ..exceptions import BotError
from ..io.base import AbstractInSource, AbstractIOSource, AbstractOutSource
from ..log.base import GenericLogger, Logger, NullLogger
from ..plugin.base import Plugin
from ..plugin.ipc import IPCManager
from ..plugin.load import PluginLoader
from ..protocol import ProtocolStack
from ..typ import AsyncCallable, P
from .dispatch import Dispatcher


class BotLifeSpan(Enum):
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


class Bot:
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
        return (
            f'Bot(name="{self.name}", '
            f"plugins_num={len(self._plugins.values())}, "
            f"handlers_num={sum(len(hs) for hs in self._dispatcher.handlers.values())})"
        )

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
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
        if self._inited:
            raise BotError(f"{self} 已不在初始化期，无法再添加输入源")

        self._in_srcs.setdefault(src.protocol, []).append(src)
        return self

    def add_output(self, src: AbstractOutSource) -> Bot:
        if self._inited:
            raise BotError(f"{self} 已不在初始化期，无法再添加输出源")

        self._out_srcs.setdefault(src.protocol, []).append(src)
        return self

    def add_io(self, src: AbstractIOSource) -> Bot:
        self.add_input(src)
        self.add_output(src)
        return self

    def add_adapter(self, adapter: Adapter) -> Bot:
        if self._inited:
            raise BotError(f"{self} 已不在初始化期，无法再添加适配器")
        if adapter.protocol in self.adapters:
            raise BotError(
                f"已存在协议 {adapter.protocol} 的适配器，同协议的适配器不能再添加"
            )

        self.adapters[adapter.protocol] = adapter
        return self

    def add_protocol(self, pstack: ProtocolStack) -> Bot:
        insrcs, outsrcs, adapter = pstack.inputs, pstack.outputs, pstack.adapter
        self.add_adapter(adapter)
        for isrc in insrcs:
            self.add_input(isrc)
        for osrc in outsrcs:
            self.add_output(osrc)
        return self

    def _run_init(self) -> None:
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
        for p in plugins:
            self.load_plugin(p, load_depth)

    def load_plugins_dir(self, pdir: str | PathLike[str], load_depth: int = 1) -> None:
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
        for pdir in pdirs:
            self.load_plugins_dir(pdir, load_depth)

    async def core_run(self) -> None:
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
        _safe_run(self.core_run(), debug)

    @classmethod
    def start(cls, *bots: Bot, debug: bool = False) -> None:
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
        if not self._running:
            raise BotError(f"{self} 未在运行中，不能停止运行")

        await self._life_bus.emit(BotLifeSpan.CLOSE, wait=True)
        self._rip_signal.set()

    async def restart(self) -> None:
        if MELO_PKG_RUNTIME not in os.environ:
            raise BotError(
                "启用重启功能，需要用以下命令运行 bot：python -m melobot run [*.py]"
            )

        await self.close()
        sys.exit(BotExitSignal.RESTART.value)

    def on(
        self, *period: BotLifeSpan
    ) -> Callable[[AsyncCallable[P, None]], AsyncCallable[P, None]]:
        def wrapped(func: AsyncCallable[P, None]) -> AsyncCallable[P, None]:
            for type in period:
                self._life_bus.register(type, func)
            return func

        return wrapped

    @property
    def on_loaded(self) -> Callable[[AsyncCallable[P, None]], AsyncCallable[P, None]]:
        return self.on(BotLifeSpan.LOADED)

    @property
    def on_reloaded(self) -> Callable[[AsyncCallable[P, None]], AsyncCallable[P, None]]:
        return self.on(BotLifeSpan.RELOADED)

    @property
    def on_started(self) -> Callable[[AsyncCallable[P, None]], AsyncCallable[P, None]]:
        return self.on(BotLifeSpan.STARTED)

    @property
    def on_close(self) -> Callable[[AsyncCallable[P, None]], AsyncCallable[P, None]]:
        return self.on(BotLifeSpan.CLOSE)

    @property
    def on_stopped(self) -> Callable[[AsyncCallable[P, None]], AsyncCallable[P, None]]:
        return self.on(BotLifeSpan.STOPPED)

    def get_adapter(
        self,
        protocol: LiteralString | None = None,
        filter: Callable[[Adapter], bool] | None = None,
    ) -> Adapter | None:
        if protocol:
            return self.adapters.get(protocol)
        if filter:
            for adapter in self.adapters.values():
                if filter(adapter):
                    return adapter
            return None
        raise BotError("protocol 或 filter 不能同时为空")

    def get_adapters(self, filter: Callable[[Adapter], bool]) -> set[Adapter]:
        return set(adapter for adapter in self.adapters.values() if filter(adapter))


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
