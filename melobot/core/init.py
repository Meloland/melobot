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
from ..utils.logger import generate_logger
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
        self.logger: Logger
        self.info = RuntimeInfo()
        
        self.__init_flag__ = False
        self._work: aio.Task=None
        self._linker: BotLinker
        self._responder: BotResponder
        self._dispatcher: BotDispatcher
        
        self._meta_handler = MetaEventHandler()
        self._plugins: Dict[str, BotPlugin]={}
        self._loader = PluginLoader

    def init(self, config_dir) -> None:
        if self.__init_flag__:
            raise BotException("bot 不能重复初始化")
        
        self.config = BotConfig(config_dir)
        self.logger = generate_logger(self.config.log_dir_path, self.config.log_level)
        self._linker = BotLinker(self.config.connect_host, self.config.connect_port, self.config.cooldown_time, self.logger)
        self._responder = BotResponder()
        self._dispatcher = BotDispatcher()

        self.__init_flag__ = True
        
        self.logger.info(f"melobot 核心版本：v{self.info.version}, 当前平台：{self.info.platform}")
        self.logger.info("核心配置、全局日志器已加载")
        self.logger.info("bot 核心模块初始化完成")

    def load(self, plugin_dir: str) -> None:
        if not self.__init_flag__:
            raise BotException("加载插件必须在初始化之后进行")
        
        self.logger.debug(f"尝试加载来自 {plugin_dir} 的插件")
        plugin = self._loader.load_plugin(plugin_dir, self._responder)
        target = self._plugins.get(plugin.name)
        if target is None:
            self._plugins[plugin.name] = plugin
            self.logger.info(f"成功加载插件：{plugin.name}")
        else:
            raise BotException(f"插件名称冲突。已加载的插件来自：{target.dir}，冲突的插件来自：{plugin.dir}")

    async def _run(self) -> None:
        if not self.__init_flag__:
            raise BotException("必须先初始化才能启动")
        
        all_plugins = []
        for plugin in self._plugins.values():
            all_plugins.append(*plugin.handlers)
        self._dispatcher.bind_handlers(all_plugins)

        self._responder.bind(self._linker)
        self._linker.bind(self._dispatcher, self._responder, self._meta_handler)
        
        try:
            async with self._linker:
                self._work = aio.create_task(self._linker.recv_routine())
                BOT_PROXY.bind(self.config, self._work, self._linker, self._responder, self._dispatcher)
                await self._work
        except wse.ConnectionClosed:
            pass
        except Exception as e:
            self.logger.debug(traceback.format_exc())
            self.logger.error(f"核心无法继续运行。抛出异常：{e}")
        finally:
            self.logger.info("bot 已清理运行时资源并关闭")
    
    def run(self) -> None:
        """
        一定要使用 get_event_loop，在启动前部分核心模块里初始化 asyncio 中的对象，
        已经生成了事件循环，使用 asyncio.run 将会运行一个新的事件循环
        """
        try:
            loop = aio.get_event_loop()
            loop.run_until_complete(self._run())
        except KeyboardInterrupt:
            pass

    async def close(self) -> None:
        if self._work is None:
            raise BotException("bot 尚未开始运行，无法停止")
        
        self._work.cancel()
        await self._work


melobot = MeloBot()
