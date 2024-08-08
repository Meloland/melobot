from __future__ import annotations

import asyncio
from contextlib import contextmanager
from contextvars import ContextVar, Token
from enum import Enum
from pathlib import Path

from ..adapter.base import Adapter
from ..exceptions import BotRuntimeError
from ..hook import HookBus
from ..io.base import AbstractInSource, AbstractIOSource, AbstractOutSource
from ..log import EmptyLogger, Logger, LoggerLocal
from ..meta import MetaInfo
from ..plugin.base import Plugin
from ..plugin.ipc import IPCManager
from ..plugin.load import PluginLoader
from ..protocol import ProtocolStack
from ..typing import (
    Any,
    AsyncCallable,
    Callable,
    Coroutine,
    Generator,
    ModuleType,
    P,
    PathLike,
    T,
)
from ..utils import singleton
from .dispatch import Dispatcher


class BotLifeSpan(Enum):
    LOADED = "l"
    CLOSE = "c"
    STOP = "s"


class Bot:
    BOTS: dict[str, Bot] = {}

    def __init__(self, name: str = "melobot", logger: Any = Logger("melobot")) -> None:
        if name in Bot.BOTS:
            raise BotRuntimeError(f"命名为 {name} 的 bot 实例已存在，请改名避免冲突")

        self.name = name
        self.logger = logger if logger is not None else EmptyLogger()
        self.info = MetaInfo
        self.adapters: list[Adapter] = []

        self._inputs: list[AbstractInSource] = []
        self._outputs: list[AbstractOutSource] = []
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
        self._inputs.append(src)
        return self

    def add_output(self, src: AbstractOutSource) -> Bot:
        self._outputs.append(src)
        return self

    def add_io(self, src: AbstractIOSource) -> Bot:
        self.add_input(src)
        self.add_output(src)
        return self

    def add_adapter(self, adapter: Adapter) -> Bot:
        self.adapters.append(adapter)
        return self

    def add_protocol(self, protocol: ProtocolStack) -> Bot:
        inputs, outputs, adapter = protocol.inputs, protocol.outputs, protocol.adapters
        self.add_adapter(adapter)
        for input in inputs:
            self.add_input(input)
        for output in outputs:
            self.add_output(output)
        return self

    def _run_init(self) -> None:
        # TODO: 匹配 io 源与 adapter
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
        with BotLocal().on_ctx(self):
            with LoggerLocal().on_ctx(self.logger):
                if self._running:
                    raise BotRuntimeError(f"{self} 已在运行中，不能再次启动运行")
                self._running = True

                await self._life_bus.emit(BotLifeSpan.LOADED)
                await self._rip.wait()

    async def run(self) -> None:
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
            raise BotRuntimeError("bot 实例尚未建立，此时无法获取 bot 实例")

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
