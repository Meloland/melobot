import asyncio as aio
import importlib.util
import inspect
import os
import pathlib
import sys
import traceback

import websockets.exceptions as wse

from ..meta import (
    EXIT_CLOSE,
    EXIT_RESTART,
    META_INFO,
    MODULE_MODE_FLAG,
    MODULE_MODE_SET,
)
from ..models.bot import BOT_PROXY, BotHookBus
from ..models.ipc import PluginBus, PluginStore
from ..models.plugin import Plugin
from ..types.core import IActionResponder
from ..types.exceptions import *
from ..types.models import BotLife
from ..types.typing import *
from ..types.utils import Logger
from ..utils.config import BotConfig
from ..utils.logger import get_logger
from .dispatcher import BotDispatcher
from .linker import BotLinker
from .responder import BotResponder

if sys.platform != "win32":
    import uvloop

    aio.set_event_loop_policy(uvloop.EventLoopPolicy())


class PluginLoader:
    """
    插件加载器
    """

    @classmethod
    def load_from_dir(cls, plugin_path: str) -> Plugin:
        """
        从指定插件目录加载插件
        """
        if not os.path.exists(os.path.join(plugin_path, "__init__.py")):
            raise PluginLoadError(
                f"{plugin_path} 缺乏入口主文件 __init__.py，插件无法加载"
            )
        plugin_name = os.path.basename(plugin_path)
        plugins_folder = str(pathlib.Path(plugin_path).parent.resolve(strict=True))
        plugins_folder_name = os.path.basename(plugins_folder)
        if plugins_folder not in sys.path:
            importlib.import_module(plugins_folder_name)
            sys.path.insert(0, plugins_folder)
        module = importlib.import_module(
            f"{plugins_folder_name}.{plugin_name}", f"{plugins_folder_name}"
        )

        plugin_class = None
        for obj in module.__dict__.values():
            if (
                isinstance(obj, type)
                and issubclass(obj, Plugin)
                and obj.__name__ != Plugin.__name__
            ):
                plugin_class = obj
                break
        if plugin_class is None:
            raise PluginLoadError(
                "指定的入口主文件中，未发现继承 Plugin 的插件类，无法加载插件"
            )
        plugin = plugin_class()
        file_path = inspect.getfile(module)
        return (plugin, file_path)

    @classmethod
    def load_from_type(cls, _class: Type[Plugin]) -> Plugin:
        """
        从插件类对象加载插件
        """
        plugin = _class()
        file_path = inspect.getfile(_class)
        return (plugin, file_path)

    @classmethod
    def load(
        cls,
        plugin_target: Union[str, Type[Plugin]],
        logger: Logger,
        responder: IActionResponder,
    ) -> Plugin:
        """
        加载插件
        """
        if isinstance(plugin_target, str):
            plugin, file_path = cls.load_from_dir(plugin_target)
        else:
            plugin, file_path = cls.load_from_type(plugin_target)
        root_path = pathlib.Path(file_path).parent.resolve(strict=True)
        plugin._Plugin__build(root_path, logger, responder)
        return plugin


class MeloBot:
    """
    bot 模块。负责整个 bot 的启动、加载和管理。
    指定 restart_tip 可在重启时自动回复
    """

    def __init__(self) -> None:
        self.config: BotConfig
        self.info = META_INFO
        # 不要更改这个属性名
        self._logger: Logger = None

        self.life: aio.Task = None
        self.plugins: Dict[str, Plugin] = {}
        self.loader = PluginLoader

        self.linker: BotLinker
        self.responder: BotResponder
        self.dispatcher: BotDispatcher
        self.plugin_bus = PluginBus
        self.plugin_store = PluginStore
        self.bot_bus = BotHookBus
        self.proxy = BOT_PROXY

        self.__init_flag__ = False
        self.exit_code = EXIT_CLOSE

    @property
    def loop(self) -> aio.AbstractEventLoop:
        return aio.get_running_loop()

    @property
    def slack(self) -> bool:
        return self.linker.slack

    @slack.setter
    def slack(self, value: bool) -> None:
        self.linker.slack = value

    @property
    def logger(self) -> Logger:
        return self._logger if self._logger else get_logger()

    def init(self, config_dir) -> None:
        """
        为 bot 核心加载配置文件
        """
        if self.__init_flag__:
            self.logger.error("bot 不能重复初始化")
            exit(self.exit_code)

        self.config = BotConfig(config_dir)
        self._logger = get_logger(self.config.log_dir_path, self.config.log_level)
        self.linker = BotLinker(
            self.config.connect_host,
            self.config.connect_port,
            self.config.max_conn_try,
            self.config.conn_try_interval,
            self.config.cooldown_time,
            self.logger,
        )
        self.responder = BotResponder(self.logger)
        self.dispatcher = BotDispatcher(self.logger)
        self.plugin_bus._bind(self.logger, self.responder)
        self.bot_bus._bind(self.logger, self.responder)

        self.logger.info("欢迎使用 melobot v2")
        self.logger.info(
            f"melobot 在 AGPL3 协议下开源发行。更多请参阅：{self.info.PROJ_SRC}"
        )
        self.logger.info(f"运行版本：{self.info.VER}，平台：{self.info.PLATFORM}")
        if os.environ.get(MODULE_MODE_FLAG) == MODULE_MODE_SET:
            self.logger.info("当前运行模式：模块运行模式")
        else:
            self.logger.info("当前运行模式：脚本运行模式")
        self.logger.info("bot 核心初始化完成")
        self.__init_flag__ = True

    def load_plugin(self, plugin_target: Union[str, Type[Plugin]]) -> None:
        """
        为 bot 加载运行插件。支持传入插件起始目录字符串（绝对路径）或插件类
        """
        if not self.__init_flag__:
            self.logger.error("加载插件必须在初始化之后进行")
            exit(self.exit_code)

        plugin_dir = (
            inspect.getfile(plugin_target)
            if not isinstance(plugin_target, str)
            else plugin_target
        )
        self.logger.debug(f"尝试加载来自 {plugin_dir} 的插件")
        plugin = self.loader.load(plugin_target, self.logger, self.responder)
        exist_plugin = self.plugins.get(plugin.__class__.__id__)
        if exist_plugin is None:
            self.plugins[plugin.__class__.__id__] = plugin
            self.dispatcher.add_handlers(plugin._Plugin__handlers)
            self.logger.info(f"成功加载插件：{plugin.__class__.__id__}")
        else:
            self.logger.error(
                f"加载插件出错：插件名称重复, 尝试加载：{plugin_dir}，已加载：{exist_plugin.plugin_dir}"
            )
            exit(self.exit_code)

    def load_plugins(self, plugins_dir: str) -> None:
        """
        从插件目录加载多个 bot 运行插件。但必须遵循标准插件格式
        """
        items = os.listdir(plugins_dir)
        for item in items:
            path = os.path.join(plugins_dir, item)
            if os.path.isdir(path) and os.path.basename(path) != "__pycache__":
                self.load_plugin(path)

    async def _run(self) -> None:
        if len(self.plugins) == 0:
            self.logger.warning("没有加载任何插件，bot 将不会有任何操作")

        await self.bot_bus.emit(BotLife.LOADED)
        self.responder.bind(self.linker)
        self.linker.bind(self.dispatcher, self.responder)
        try:
            async with self.linker:
                self.life = aio.create_task(self.linker.listen())
                self.proxy._bind(self)
                self.logger.info("bot 开始正常运行")
                await self.life
        except wse.ConnectionClosed:
            pass
        except Exception as e:
            self.logger.error(f"bot 核心无法继续运行。异常：{e}")
            self.logger.debug("异常回溯栈：\n" + traceback.format_exc().strip("\n"))
        finally:
            await self.bot_bus.emit(BotLife.BEFORE_STOP, wait=True)
            self.logger.info("bot 已清理运行时资源并关闭")
            exit(self.exit_code)

    def run(self) -> None:
        """
        运行 bot
        """
        if not self.__init_flag__:
            self.logger.error("必须先初始化才能启动")
            exit(self.exit_code)
        try:
            """
            一定要手动设置事件循环。在启动前，部分核心模块初始化异步对象，
            已经生成了事件循环，不设置而直接使用 asyncio.run 将会运行一个新的事件循环，
            不同事件循环的异步对象无法直接通信
            """
            aio.set_event_loop(aio.get_event_loop())
            # 使用 asyncio.run 可以保证发生各种异常时一定取消所有任务（包括键盘中断）
            aio.run(self._run())
        except KeyboardInterrupt:
            pass

    async def close(self) -> None:
        """
        停止 bot
        """
        if self.life is None:
            self.logger.error("bot 尚未运行，无需停止")
            exit(self.exit_code)
        await self.bot_bus.emit(BotLife.BEFORE_CLOSE, wait=True)
        self.life.cancel()

    async def restart(self) -> None:
        """
        重启 bot
        """
        if self.life is None:
            self.logger.error("bot 尚未运行，无需重启")
            exit(self.exit_code)
        if os.environ.get(MODULE_MODE_FLAG) != MODULE_MODE_SET:
            self.logger.error("只有在模块运行模式下，才能使用 bot 重启功能")
            return
        self.logger.info("bot 即将进行重新启动...")
        self.exit_code = EXIT_RESTART
        self.life.cancel()
