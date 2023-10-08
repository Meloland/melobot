import asyncio as aio
import os
import sys
import traceback
from logging import Logger

import websockets.exceptions as wse

from ..interface.core import IMetaDispatcher
from ..interface.typing import *
from ..models.event import MetaEvent
from ..models.exceptions import *
from ..utils.config import BotConfig
from ..utils.logger import get_logger
from .bot import BOT_PROXY
from .dispatcher import BotDispatcher
from .linker import BotLinker
from .plugin import BotPlugin, PluginLoader
from .responder import BotResponder

if sys.platform != 'win32':
    import uvloop
    aio.set_event_loop_policy(uvloop.EventLoopPolicy())


class MetaEventHandler(IMetaDispatcher):
    def __init__(self) -> None:
        super().__init__()

    async def dispatch(self, metaEvent: MetaEvent) -> None:
        pass


class RuntimeInfo:
    def __init__(self) -> None:
        self.version = '2.0.0-Beta1'
        self.proj_name = 'MeloBot'
        self.author = 'AiCorein'
        self.proj_url = 'https://github.com/AiCorein/Qbot-MeloBot'
        self.platform = sys.platform
        self.os_sep = os.sep
        self.os_pathsep = os.pathsep


class MeloBot:
    """
    bot 模块。负责整个 bot 的启动、加载和管理
    """
    def __init__(self) -> None:
        self.config: BotConfig
        self.info = RuntimeInfo()
        self._logger: Logger=None
        
        self.__init_flag__ = False
        self._initd: aio.Task=None
        self._linker: BotLinker
        self._responder: BotResponder
        self._dispatcher: BotDispatcher
        
        self._meta_handler = MetaEventHandler()
        self._plugins: Dict[str, BotPlugin]={}
        self._loader = PluginLoader

    @property
    def logger(self) -> Logger:
        return self._logger if self._logger else get_logger()

    def init(self, config_dir) -> None:
        if self.__init_flag__:
            self.logger.error("bot 不能重复初始化")
            sys.exit(0)
        
        self.config = BotConfig(config_dir)
        self._logger = get_logger(self.config.log_dir_path, self.config.log_level)
        self._linker = BotLinker(self.config.connect_host, self.config.connect_port, self.config.cooldown_time, self.logger)
        self._responder = BotResponder()
        self._dispatcher = BotDispatcher()

        self.__init_flag__ = True
        self.logger.info(f"运行版本：{self.info.version}，平台：{self.info.platform}")
        self.logger.info("bot 核心配置、日志器已加载，初始化完成")

    def load(self, plugin_dir: str) -> None:
        fault_flag = False
        if not self.__init_flag__:
            self.logger.error("加载插件必须在初始化之后进行")
            fault_flag = True
        
        self.logger.debug(f"尝试加载来自 {plugin_dir} 的插件")
        try:
            plugin = self._loader.load_plugin(plugin_dir, self._responder)
            target = self._plugins.get(plugin.name)
            if target is None:
                self._plugins[plugin.name] = plugin
                self.logger.info(f"成功加载插件：{plugin.name}")
            else:
                raise BotException("插件名称重复")
        except BotException as e:
            self.logger.error(f"加载插件出错：{e.origin_err}, 来源：{plugin_dir}")
            fault_flag = True

        if fault_flag:
            sys.exit(0)

    async def _run(self) -> None:
        if not self.__init_flag__:
            self.logger.error("必须先初始化才能启动")
            sys.exit(0)
        if len(self._plugins) == 0:
            self.logger.warning("没有加载任何插件，bot 将不会有任何操作")
        
        all_plugins = []
        for plugin in self._plugins.values():
            all_plugins.extend(plugin.handlers)
        self._dispatcher.bind_handlers(all_plugins)

        self._responder.bind(self._linker)
        self._linker.bind(self._dispatcher, self._responder, self._meta_handler)
        
        try:
            async with self._linker:
                self._initd = aio.create_task(self._linker.recv_routine())
                BOT_PROXY._bind(self.config, self._initd, self._linker, self._responder, self._dispatcher)
                await self._initd
        except wse.ConnectionClosed:
            pass
        except Exception as e:
            self.logger.debug(traceback.format_exc())
            self.logger.error(f"bot 核心无法继续运行。抛出异常：{e}")
        finally:
            self.logger.info("bot 已清理运行时资源并关闭")
    
    def run(self) -> None:
        try:
            """
            一定要使用 get_event_loop，在启动前部分核心模块里初始化 asyncio 中的对象，
            已经生成了事件循环，使用 asyncio.run 将会运行一个新的事件循环
            """
            loop = aio.get_event_loop()
            loop.run_until_complete(self._run())
        except KeyboardInterrupt:
            self.logger.info("bot 已清理运行时资源并关闭")

    async def close(self) -> None:
        if self._initd is None:
            self.logger.error("bot 尚未开始运行，无法停止")
            sys.exit(0)
        self._initd.cancel()
        await self._initd


melobot = MeloBot()
melobot.logger.info("欢迎使用 melobot v2")
melobot.logger.info(f"本项目在 AGPL3 协议下开源发行。更多请参阅：{melobot.info.proj_url}")
