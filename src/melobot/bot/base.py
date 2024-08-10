from __future__ import annotations

import asyncio
import os
import sys
from contextlib import contextmanager
from contextvars import ContextVar, Token
from enum import Enum
from pathlib import Path

from ..adapter.base import Adapter
from ..exceptions import BotRuntimeError
from ..hook import HookBus
from ..io.base import AbstractInSource, AbstractIOSource, AbstractOutSource
from ..log import EmptyLogger, Logger, LoggerLocal
from ..plugin.base import Plugin
from ..plugin.ipc import IPCManager
from ..plugin.load import PluginLoader
from ..protocol import Protocol
from ..types import (
    Any,
    AsyncCallable,
    Callable,
    Coroutine,
    Generator,
    ModuleType,
    P,
    PathLike,
)
from ..utils import singleton
from .dispatch import Dispatcher


class BotLifeSpan(Enum):
    LOADED = "l"
    RELOADED = "r"
    CLOSE = "c"
    STOP = "s"


class BotExitSignal(Enum):
    NORMAL_STOP = 0
    ERROR = 1
    RESTART = 2


MELO_PKG_RUNTIME = "MELOBOT_PKG_RUNTIME"
MELO_LAST_EXIT_SIGNAL = "MELO_LAST_EXIT_SIGNAL"


class Bot:
    __instances__: dict[str, Bot] = {}

    def __new__(cls, name: str = "melobot", *args, **kwargs) -> Bot:
        if name in Bot.__instances__:
            raise BotRuntimeError(f"命名为 {name} 的 bot 实例已存在，请改名避免冲突")
        obj = super().__new__(cls)
        Bot.__instances__[name] = obj
        return obj

    def __init__(self, name: str = "melobot", logger: Any = Logger("melobot")) -> None:
        self.name = name
        self.logger = logger if logger is not None else EmptyLogger()
        self.adapters: dict[str, Adapter] = {}

        self._in_srcs: dict[str, list[AbstractInSource]] = {}
        self._out_srcs: dict[str, list[AbstractOutSource]] = {}
        self._ipc_manager = IPCManager()
        self._loader = PluginLoader()
        self._plugins: dict[str, Plugin] = {}
        self._life_bus = HookBus[BotLifeSpan](BotLifeSpan)
        self._dispatcher = Dispatcher()

        self._inited = False
        self._running = False
        self._rip = asyncio.Event()

    def __repr__(self) -> str:
        return f'Bot(name="{self.name}")'

    def add_input(self, src: AbstractInSource) -> Bot:
        if self._inited:
            raise BotRuntimeError(f"{self} 已不在初始化期，无法再添加输入源")

        self._in_srcs.setdefault(src.protocol, []).append(src)
        return self

    def add_output(self, src: AbstractOutSource) -> Bot:
        if self._inited:
            raise BotRuntimeError(f"{self} 已不在初始化期，无法再添加输出源")

        self._out_srcs.setdefault(src.protocol, []).append(src)
        return self

    def add_io(self, src: AbstractIOSource) -> Bot:
        self.add_input(src)
        self.add_output(src)
        return self

    def add_adapter(self, adapter: Adapter) -> Bot:
        if self._inited:
            raise BotRuntimeError(f"{self} 已不在初始化期，无法再添加适配器")
        if adapter.protocol in self.adapters:
            raise BotRuntimeError(
                f"已存在协议 {adapter.protocol} 的适配器，同协议的适配器不能再添加"
            )

        self.adapters[adapter.protocol] = adapter
        return self

    def add_protocol(self, protocol: Protocol) -> Bot:
        insrcs, outsrcs, adapter = protocol.inputs, protocol.outputs, protocol.adapter
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

    def load_plugin(self, plugin: ModuleType | str | PathLike[str]) -> Bot:
        if not self._inited:
            self._run_init()

        with BotLocal().on_ctx(self):
            with LoggerLocal().on_ctx(self.logger):
                if isinstance(plugin, ModuleType):
                    p_name = plugin.__name__
                else:
                    p_name = Path(plugin).resolve().parts[-1]
                if p_name in self._plugins:
                    raise BotRuntimeError(
                        f"尝试加载的插件 {p_name} 与其他已加载的 melobot 插件重名，请修改名称（修改插件目录名）"
                    )

                p = self._loader.load(plugin)
                self._plugins[p.name] = p
                self._dispatcher.no_ctrl_add(*p.handlers)
                for share in p.shares:
                    self._ipc_manager.add(p.name, share)
                for func in p.funcs:
                    self._ipc_manager.add_func(p.name, func)
                self.logger.info(f"成功加载插件：{p.name}")

                return self

    def load_plugins(self, *plugin: ModuleType | str | PathLike[str]) -> None:
        for p in plugin:
            self.load_plugin(p)

    async def _run(self) -> None:
        try:
            with BotLocal().on_ctx(self):
                with LoggerLocal().on_ctx(self.logger):
                    if self._running:
                        raise BotRuntimeError(f"{self} 已在运行中，不能再次启动运行")
                    self._running = True

                    if (
                        MELO_LAST_EXIT_SIGNAL in os.environ
                        and int(os.environ[MELO_LAST_EXIT_SIGNAL])
                        == BotExitSignal.RESTART.value
                    ):
                        await self._life_bus.emit(BotLifeSpan.RELOADED)
                    else:
                        await self._life_bus.emit(BotLifeSpan.LOADED)
                    for adapter in self.adapters.values():
                        asyncio.create_task(adapter._run())
                    await self._rip.wait()
        finally:
            for task in asyncio.all_tasks():
                task.cancel()
            await self._life_bus.emit(BotLifeSpan.STOP, wait=True)
            self.logger.info(f"{self} 已停止运行")
            self._running = False

    def run(self) -> None:
        _safe_blocked_run(self._run())

    @classmethod
    def start(cls, *bots: Bot) -> None:
        async def bots_run():
            tasks = []
            for bot in bots:
                tasks.append(asyncio.create_task(bot._run()))
            try:
                await asyncio.wait(tasks)
            except asyncio.CancelledError:
                pass

        _safe_blocked_run(bots_run())

    async def close(self) -> None:
        if not self._running:
            raise BotRuntimeError(f"{self} 未在运行中，不能停止运行")

        await self._life_bus.emit(BotLifeSpan.CLOSE, wait=True)
        self._rip.set()

    async def restart(self) -> None:
        if MELO_PKG_RUNTIME not in os.environ:
            raise BotRuntimeError(
                "启用重启功能，需要用以下命令运行 bot：python -m melobot run [*.py]"
            )

        await self.close()
        sys.exit(BotExitSignal.RESTART.value)

    def on(
        self, *types: BotLifeSpan
    ) -> Callable[[AsyncCallable[P, None]], AsyncCallable[P, None]]:
        def wrapped(func: AsyncCallable[P, None]) -> AsyncCallable[P, None]:
            for type in types:
                self._life_bus.register(type, func)
            return func

        return wrapped

    @property
    def on_loaded(self) -> Callable[[AsyncCallable[P, None]], AsyncCallable[P, None]]:
        return self.on(BotLifeSpan.LOADED)

    @property
    def on_close(self) -> Callable[[AsyncCallable[P, None]], AsyncCallable[P, None]]:
        return self.on(BotLifeSpan.CLOSE)

    @property
    def on_stop(self) -> Callable[[AsyncCallable[P, None]], AsyncCallable[P, None]]:
        return self.on(BotLifeSpan.STOP)


def _safe_blocked_run(main: Coroutine[Any, Any, None]) -> None:
    try:
        asyncio.set_event_loop(asyncio.get_event_loop())
        asyncio.run(main)
    except KeyboardInterrupt:
        pass
    except asyncio.CancelledError:
        pass


@singleton
class BotLocal:
    """bot 实例自动上下文"""

    def __init__(self) -> None:
        object.__setattr__(self, "__storage__", ContextVar("bot_ctx"))
        self.__storage__: ContextVar["Bot"]

    def get(self) -> Bot:
        try:
            return self.__storage__.get()
        except LookupError:
            raise BotRuntimeError("此时未初始化 bot 实例，无法获取")

    def add(self, ctx: Bot) -> Token:
        return self.__storage__.set(ctx)

    def remove(self, token: Token) -> None:
        self.__storage__.reset(token)

    @contextmanager
    def on_ctx(self, obj: Bot) -> Generator[None, None, None]:
        token = self.add(obj)
        try:
            yield
        finally:
            self.remove(token)


def get_bot() -> Bot:
    return BotLocal().get()
