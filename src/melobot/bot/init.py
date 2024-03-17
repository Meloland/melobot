import asyncio as aio
import inspect
import os
import sys
from copy import deepcopy

from ..context.session import BotSessionManager
from ..controller.dispatcher import BotDispatcher
from ..controller.responder import BotResponder
from ..meta import MetaInfo
from ..models.event import BotEventBuilder
from ..plugin.handler import EVENT_HANDLER_MAP
from ..plugin.init import BotPlugin, PluginLoader, PluginProxy
from ..plugin.ipc import PluginBus, PluginStore
from ..types.abc import BOT_LOCAL, AbstractConnector
from ..types.exceptions import BotRuntimeError, DuplicateError, get_better_exc
from ..types.tools import get_rich_str
from ..types.typing import BotLife, Literal, Optional
from ..utils.logger import BotLogger, Logger, NullLogger
from .hook import BotHookBus

if sys.platform != "win32":
    import uvloop

    aio.set_event_loop_policy(uvloop.EventLoopPolicy())


class MeloBot:
    """MeloBot 类。实例化创建一个新的 bot"""

    BOTS: dict[str, "MeloBot"] = {}

    @classmethod
    def start(cls, *bots: "MeloBot") -> None:
        async def bots_run():
            tasks = []
            for bot in bots:
                tasks.append(aio.create_task(bot._run()))
            await aio.wait(tasks)

        try:
            aio.set_event_loop(aio.get_event_loop())
            aio.run(bots_run())
        except KeyboardInterrupt:
            pass

    def __init__(self, name: str) -> None:
        if name in MeloBot.BOTS.keys():
            raise DuplicateError(f"命名为 {name} 的 bot 实例已存在，请改名避免冲突")
        MeloBot.BOTS[name] = self

        self._loader = PluginLoader
        self._ctx_manager = BotSessionManager
        self._event_builder = BotEventBuilder

        self.name = name
        self.info = MetaInfo()
        self.life: list[aio.Task]
        self.logger: Logger
        self.connector: AbstractConnector

        self.__plugins: dict[str, BotPlugin] = {}
        self._plugin_store = PluginStore()
        self._plugin_bus = PluginBus()
        self._bot_bus = BotHookBus()
        self._responder = BotResponder()
        self._dispatcher = BotDispatcher()

        self.__init_flag__: bool = False
        self.__run_flag__: bool = False

    def init(
        self,
        connector: AbstractConnector,
        enable_log: bool = True,
        logger_name: Optional[str] = None,
        log_level: Literal["DEBUG", "ERROR", "INFO", "WARNING", "CRITICAL"] = "INFO",
        log_to_console: bool = True,
        log_to_dir: Optional[str] = None,
    ) -> None:
        if connector._ref_flag:
            raise DuplicateError(
                "bot 初始化时，不可使用已被其他 bot 实例使用的连接适配器"
            )
        self.connector = connector
        self.connector._ref_flag = True
        if not enable_log:
            self.logger = NullLogger(f"__NULL_{self.name}__")
        else:
            self.logger = BotLogger(
                self.name if logger_name is None else logger_name,
                log_level,
                log_to_console,
                log_to_dir,
            )

        self._dispatcher._bind(
            EVENT_HANDLER_MAP, self._bot_bus, self._ctx_manager, self.logger
        )
        self._plugin_bus._bind(self.logger)
        self._bot_bus._bind(self.logger)
        self._responder._bind(self.logger, self.connector)
        self.connector._bind(
            self._dispatcher,
            self._responder,
            self._event_builder,
            self._bot_bus,
            self.logger,
        )
        self.logger.debug("bot 初始化完成，各核心组件已初始化")
        self.__init_flag__ = True

    def load_plugin(self, plugin_target: str | BotPlugin) -> None:
        """
        为 bot 加载运行插件。支持传入插件起始目录字符串（绝对路径）或插件类
        """
        if not self.__init_flag__:
            raise BotRuntimeError("bot 尚未初始化，不能加载插件")

        plugin_dir = None if not isinstance(plugin_target, str) else plugin_target
        if plugin_dir is None:
            self.logger.debug(f"尝试加载插件 {plugin_target}")
        else:
            self.logger.debug(f"尝试加载来自 {plugin_dir} 的插件")
        plugin = self._loader.load(plugin_target)
        exist_plugin = self.__plugins.get(plugin.__id__)
        if exist_plugin is not None:
            self.logger.error(
                f"加载插件出错：插件名称重复, 重复的名称为：{plugin.__id__}"
            )
            return

        handlers = []
        for _ in plugin.__handler_args__:
            handler = _.type(_.executor, plugin, self.logger, *_.params)
            self._ctx_manager.register(handler)
            handlers.append(handler)
        for _ in plugin.__share_args__:
            self._plugin_store.create_so(_.reflector, _.namespace, _.id)
        for _ in plugin.__share_cb_args__:
            self._plugin_store.bind_cb(_.namespace, _.id, _.cb)
        for _ in plugin.__signal_args__:
            self._plugin_bus.register(_.namespace, _.signal, _.func)
        for _ in plugin.__hook_args__:
            self._bot_bus.register(_.type, _.func)

        self.__plugins[plugin.__id__] = plugin
        self._dispatcher.add_handlers(handlers)
        self.logger.info(f"成功加载插件：{plugin.__id__}")

    def load_plugins(self, plugins_dir: str) -> None:
        if not self.__init_flag__:
            raise BotRuntimeError("bot 尚未初始化，不能加载插件")

        self.logger.debug(f"尝试从目录 {plugins_dir} 批量加载插件")
        items = os.listdir(plugins_dir)
        for item in items:
            path = os.path.join(plugins_dir, item)
            if os.path.isdir(path) and os.path.basename(path) != "__pycache__":
                self.load_plugin(path)

    async def _run(self) -> None:
        if not self.__init_flag__:
            raise BotRuntimeError("bot 尚未初始化，不能启动")
        if self.__run_flag__:
            raise BotRuntimeError("bot 已在运行，无需再次启动")
        if len(self.__plugins) == 0:
            self.logger.warning("没有加载任何插件，bot 将不会有任何操作")

        ctx_token = BOT_LOCAL._add_ctx(self)
        await self._bot_bus.emit(BotLife.LOADED)
        self.logger.debug("LOADED hook 已完成")
        try:
            async with self.connector:
                self._dispatcher._set_ready()
                self._responder._set_ready()
                self.connector._set_ready()
                self.life = await self.connector._start_tasks()
                self.__run_flag__ = True
                self.logger.info("bot 开始正常运行")
                await aio.wait(self.life)
        except Exception as e:
            self.logger.error(f"bot 核心无法继续运行。异常：{e}")
            self.logger.error("异常回溯栈：\n" + get_better_exc(e))
            self.logger.error("异常点局部变量：\n" + get_rich_str(locals()))
        finally:
            await self._bot_bus.emit(BotLife.BEFORE_STOP, wait=True)
            self.logger.debug("BEFORE_STOP hook 已完成")
            self.logger.info("bot 已清理运行时资源")
            BOT_LOCAL._del_ctx(ctx_token)
            self.__run_flag__ = False

    def run(self) -> None:
        try:
            aio.set_event_loop(aio.get_event_loop())
            aio.run(self._run())
        except KeyboardInterrupt:
            pass

    async def close(self) -> None:
        """
        停止 bot
        """
        if not self.__run_flag__:
            raise BotRuntimeError("bot 尚未运行，无需停止")

        await self._bot_bus.emit(BotLife.BEFORE_CLOSE, wait=True)
        self.logger.debug("BEFORE_CLOSE hook 已完成")
        for task in self.life:
            task.cancel()

    def is_activate(self) -> bool:
        if not self.__init_flag__:
            raise BotRuntimeError("bot 尚未初始化，不能执行此方法")

        return not self.connector.slack

    def activate(self) -> None:
        if not self.__init_flag__:
            raise BotRuntimeError("bot 尚未初始化，不能执行此方法")

        self.connector.slack = False

    def slack(self) -> None:
        """
        使 bot 不再发送 action。但 ACTION_PRESEND 钩子依然会触发
        """
        if not self.__init_flag__:
            raise BotRuntimeError("bot 尚未初始化，不能执行此方法")

        self.connector.slack = True

    def get_plugins(self) -> dict[str, PluginProxy]:
        """
        获取 bot 当前所有插件信息
        """
        if not self.__init_flag__:
            raise BotRuntimeError("bot 尚未初始化，不能执行此方法")

        return {name: deepcopy(p.__proxy__) for name, p in self.__plugins.items()}

    def emit_signal(
        self, namespace: str, signal: str, *args, wait: bool = False, **kwargs
    ):
        if not self.__init_flag__:
            raise BotRuntimeError("bot 尚未初始化，不能执行此方法")

        return self._plugin_bus.emit(namespace, signal, *args, wait=wait, **kwargs)

    def get_share(self, namespace: str, id: str):
        if not self.__init_flag__:
            raise BotRuntimeError("bot 尚未初始化，不能执行此方法")

        return self._plugin_store.get(namespace, id)
