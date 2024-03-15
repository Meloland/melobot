import asyncio as aio
import inspect
import os
import sys

from ..context.session import BotSessionManager
from ..controller.dispatcher import BotDispatcher
from ..controller.responder import BotResponder
from ..meta import MetaInfo
from ..models.event import BotEventBuilder
from ..plugin.handler import EVENT_HANDLER_MAP
from ..plugin.init import Plugin, PluginLoader, PluginProxy
from ..plugin.ipc import PluginBus, PluginStore
from ..types.abc import BOT_LOCAL, AbstractConnector
from ..types.exceptions import *
from ..types.tools import get_rich_str
from ..types.typing import *
from ..utils.logger import BotLogger, NullLogger
from .hook import BotHookBus

if sys.platform != "win32":
    import uvloop

    aio.set_event_loop_policy(uvloop.EventLoopPolicy())


class MeloBot:
    """MeloBot 类。实例化创建一个新的 bot"""

    BOTS: dict[str, "MeloBot"] = {}
    PENDING_BOTS: dict[str, "MeloBot"] = {}

    @classmethod
    def get(cls, name: str) -> "MeloBot":
        if name not in cls.BOTS.keys():
            raise BotRuntimeError(f"目前不存在名为 {name} 的 bot 实例")
        else:
            return cls.BOTS[name]

    @classmethod
    def get_ref(cls, name: str) -> "MeloBot":
        if name not in cls.PENDING_BOTS.keys():
            try:
                MeloBot(name)
                bot = cls.BOTS.pop(name)
                cls.PENDING_BOTS[name] = bot
                bot.__wild_flag__ = True
                return bot
            except DuplicateError:
                raise DuplicateError(
                    f"名为 {name} 的 bot 实例已存在，应该使用 get()，而不是 ger_ref()"
                )
        else:
            return cls.PENDING_BOTS[name]

    @classmethod
    def set_ref(cls, name: str) -> "MeloBot":
        if name not in cls.PENDING_BOTS.keys():
            raise BotRuntimeError(f"目前不存在名为 {name} 的悬挂 bot 实例")
        else:
            bot = cls.PENDING_BOTS.pop(name)
            cls.BOTS[name] = bot
            bot.__wild_flag__ = False
            return bot

    @classmethod
    def start(cls, *bots: "MeloBot") -> None:
        async def bots_run():
            tasks = []
            for bot in bots:
                tasks.append(aio.create_task(bot.run()))
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

        self.__plugins: Dict[str, Plugin] = {}
        self._loader = PluginLoader
        self._ctx_manager = BotSessionManager
        self._event_builder = BotEventBuilder

        self.name = name
        self.info = MetaInfo()
        self.life: list[aio.Task]
        self.logger: BotLogger
        self.plugin_store = PluginStore()
        self.plugin_bus = PluginBus()
        self.connector: AbstractConnector

        self._bot_bus = BotHookBus()
        self._responder = BotResponder()
        self._dispatcher = BotDispatcher()

        self.__init_flag__: bool = False
        self.__run_flag__: bool = False
        self.__wild_flag__: bool = False

    def init(
        self,
        connector: AbstractConnector,
        enable_log: bool = True,
        logger_name: str = None,
        log_level: Literal["DEBUG", "ERROR", "INFO", "WARNING", "CRITICAL"] = "INFO",
        log_to_console: bool = True,
        log_to_dir: Optional[str] = None,
    ) -> None:
        if self.__wild_flag__:
            raise BotRuntimeError("无法初始化一个悬挂状态的 bot")

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
        self.plugin_bus._bind(self.logger)
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

    def load_plugin(self, plugin_target: str | Type[Plugin]) -> None:
        """
        为 bot 加载运行插件。支持传入插件起始目录字符串（绝对路径）或插件类
        """
        if not self.__init_flag__:
            raise BotRuntimeError("bot 尚未初始化，不能加载插件")

        plugin_dir = (
            inspect.getfile(plugin_target)
            if not isinstance(plugin_target, str)
            else plugin_target
        )
        self.logger.debug(f"尝试加载来自 {plugin_dir} 的插件")
        plugin = self._loader.load(
            plugin_target,
            self.logger,
            self.plugin_store,
            self.plugin_bus,
            self._bot_bus,
        )
        exist_plugin = self.__plugins.get(plugin.ID)
        if exist_plugin is None:
            self.__plugins[plugin.ID] = plugin
            self._dispatcher.add_handlers(plugin._handlers)
            self.logger.info(f"成功加载插件：{plugin.ID}")
        else:
            self.logger.error(
                f"加载插件出错：插件名称重复, 尝试加载：{plugin_dir}，已加载：{exist_plugin.plugin_dir}"
            )

    def load_plugins(self, plugins_dir: str) -> None:
        if not self.__init_flag__:
            raise BotRuntimeError("bot 尚未初始化，不能加载插件")

        self.logger.debug(f"尝试从目录 {plugins_dir} 批量加载插件")
        items = os.listdir(plugins_dir)
        for item in items:
            path = os.path.join(plugins_dir, item)
            if os.path.isdir(path) and os.path.basename(path) != "__pycache__":
                self.load_plugin(path)

    async def run(self) -> None:
        if not self.__init_flag__:
            raise BotRuntimeError("bot 尚未初始化，不能启动")
        if self.__run_flag__:
            raise BotRuntimeError("bot 已在运行，无需再次启动")

        if len(self.__plugins) == 0:
            self.logger.warning("没有加载任何插件，bot 将不会有任何操作")

        b_token = BOT_LOCAL._add_ctx(self)
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
            BOT_LOCAL._del_ctx(b_token)
            self.__run_flag__ = False

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

    def get_logger(self) -> "BotLogger":
        """
        获得 bot 全局日志器
        """
        if not self.__init_flag__:
            raise BotRuntimeError("bot 尚未初始化，不能执行此方法")

        return self.logger

    def get_plugins(self) -> dict[str, PluginProxy]:
        """
        获取 bot 当前所有插件信息
        """
        if not self.__init_flag__:
            raise BotRuntimeError("bot 尚未初始化，不能执行此方法")

        return {name: p._proxy for name, p in self.__plugins.items()}

    def on_signal(self, namespace: str, signal: str):
        return self.plugin_bus.on(namespace, signal)

    def emit_signal(
        self, namespace: str, signal: str, *args, wait: bool = False, **kwargs
    ):
        return self.plugin_bus.emit(namespace, signal, *args, wait=wait, **kwargs)

    def get_share(self, namespace: str, id: str):
        return self.plugin_store.get(namespace, id)

    def share_echo(self, namespace: str, id: str):
        return self.plugin_store.echo(namespace, id)

    def on_lifecycle(self, hook_type: BotLife):
        return self._bot_bus.on(hook_type)

    def on_loaded(self):
        """
        用作装饰器，不传入 callback 参数，可注册一个 LOADED 生命周期 hook 方法

        也可直接调用此方法，传入 callback 参数来注册一个 hook 方法
        """
        return self.on_lifecycle(BotLife.LOADED)

    def on_connected(self):
        """
        用作装饰器，不传入 callback 参数，可注册一个 CONNECTED 生命周期 hook 方法

        也可直接调用此方法，传入 callback 参数来注册一个 hook 方法
        """
        return self.on_lifecycle(BotLife.CONNECTED)

    def on_before_close(self):
        """
        用作装饰器，不传入 callback 参数，可注册一个 BEFORE_CLOSE 生命周期 hook 方法

        也可直接调用此方法，传入 callback 参数来注册一个 hook 方法
        """
        return self.on_lifecycle(BotLife.BEFORE_CLOSE)

    def on_before_stop(self):
        """
        用作装饰器，不传入 callback 参数，可注册一个 BEFORE_STOP 生命周期 hook 方法

        也可直接调用此方法，传入 callback 参数来注册一个 hook 方法
        """
        return self.on_lifecycle(BotLife.BEFORE_STOP)

    def on_event_built(self):
        """
        用作装饰器，不传入 callback 参数，可注册一个 EVENT_BUILT 生命周期 hook 方法

        也可直接调用此方法，传入 callback 参数来注册一个 hook 方法
        """
        return self.on_lifecycle(BotLife.EVENT_BUILT)

    def on_action_presend(self):
        """
        用作装饰器，不传入 callback 参数，可注册一个 ACTION_PRESEND 生命周期 hook 方法

        也可直接调用此方法，传入 callback 参数来注册一个 hook 方法
        """
        return self.on_lifecycle(BotLife.ACTION_PRESEND)
