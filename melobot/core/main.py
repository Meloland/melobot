import asyncio as aio
import os
import sys
import traceback
import importlib.util
from logging import Logger

import websockets.exceptions as wse

from ..interface.core import IMetaDispatcher, IActionResponder
from ..interface.models import Plugin
from ..interface.typing import *
from ..models.event import MetaEvent
from ..interface.exceptions import *
from ..utils.config import BotConfig
from ..utils.logger import get_logger
from .proxy import BOT_PROXY
from .dispatcher import BotDispatcher
from .linker import BotLinker
from .responder import BotResponder

if sys.platform != 'win32':
    import uvloop
    aio.set_event_loop_policy(uvloop.EventLoopPolicy())


# TODO: 补全元事件处理器部分
class MetaEventDispatcher(IMetaDispatcher):
    def __init__(self) -> None:
        super().__init__()

    # 未来重写记得加上异常日志记录
    async def dispatch(self, meta_event: MetaEvent) -> None:
        pass


class PluginLoader:
    @classmethod
    def load_plugin(cls, dir: str, logger: Logger, responder: IActionResponder) -> Plugin:
        """
        实例化插件。并进行校验和 handlers、runners 的初始化。
        """
        if not os.path.exists(os.path.join(dir, 'main.py')):
            raise BotException("缺乏入口主文件，插件无法加载")
        main_path = os.path.join(dir, 'main.py')
        spec = importlib.util.spec_from_file_location(os.path.basename(main_path), main_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    
        plugin_class = None
        for obj in module.__dict__.values():
            if isinstance(obj, type) and issubclass(obj, Plugin) and obj.__name__ != Plugin.__name__:
                plugin_class = obj
                break
        if plugin_class is None:
            raise BotException("不存在插件类，无法加载插件")
        plugin = plugin_class()
        plugin.build(dir, logger, responder)
        return plugin


class MeloBot:
    """
    bot 模块。负责整个 bot 的启动、加载和管理
    """
    def __init__(self) -> None:
        self.config: BotConfig
        self.meta = METAINFO
        # 不要更改这个属性名
        self._logger: Logger=None

        self.life: aio.Task=None
        self._linker: BotLinker
        self._responder: BotResponder
        self._dispatcher: BotDispatcher
        self._meta_dispatcher = MetaEventDispatcher()
        self.plugins: Dict[str, Plugin]={}
        self.loader = PluginLoader

        self.__init_flag__ = False

    @property
    def logger(self) -> Logger:
        return self._logger if self._logger else get_logger()

    def init(self, config_dir) -> None:
        """
        使用配置文件初始化 bot
        """
        if self.__init_flag__:
            self.logger.error("bot 不能重复初始化")
            exit(0)
        
        self.config = BotConfig(config_dir)
        self._logger = get_logger(self.config.log_dir_path, self.config.log_level)
        self._linker = BotLinker(self.config.connect_host, self.config.connect_port, self.config.cooldown_time,
                                self.logger)
        self._responder = BotResponder(self.logger)
        self._dispatcher = BotDispatcher(self.logger)

        self.logger.info("欢迎使用 melobot v2")
        self.logger.info(f"本项目在 AGPL3 协议下开源发行。更多请参阅：{self.meta.PROJ_SRC}")
        self.logger.info(f"运行版本：{self.meta.VER}，平台：{self.meta.PLATFORM}")
        self.logger.info("bot 核心配置、日志器已加载，初始化完成")
        self.__init_flag__ = True

    def load(self, plugin_dir: str) -> None:
        """
        为 bot 加载运行插件
        """
        if not self.__init_flag__:
            self.logger.error("加载插件必须在初始化之后进行")
            exit(0)
        
        self.logger.debug(f"尝试加载来自 {plugin_dir} 的插件")
        plugin = self.loader.load_plugin(plugin_dir, self.logger, self._responder)
        target = self.plugins.get(plugin.id)
        if target is None:
            self.plugins[plugin.id] = plugin
            self.logger.info(f"成功加载插件：{plugin.id}")
        else:
            self.logger.error(f"加载插件出错：插件名称重复, 尝试加载：{plugin_dir}，已加载：{target.plugin_dir}")
            exit(0)

    async def _run(self) -> None:
        if len(self.plugins) == 0:
            self.logger.warning("没有加载任何插件，bot 将不会有任何操作")
        
        all_handlers = []
        for plugin in self.plugins.values():
            all_handlers.extend(plugin.handlers)
        self._dispatcher.bind(all_handlers)
        self._responder.bind(self._linker)
        self._linker.bind(self._dispatcher, self._responder, self._meta_dispatcher)
        
        try:
            async with self._linker:
                self.life = aio.create_task(self._linker.listen())
                BOT_PROXY._bind(self.config, self.life)
                await self.life
        except wse.ConnectionClosed:
            pass
        except Exception as e:
            self.logger.error(f"bot 核心无法继续运行。异常：{e}")
            self.logger.debug('异常回溯栈：\n' + traceback.format_exc().strip('\n'))
        finally:
            self.logger.info("bot 已清理运行时资源并关闭")
    
    def run(self) -> None:
        """
        开始运行 bot
        """
        if not self.__init_flag__:
            self.logger.error("必须先初始化才能启动")
            exit(0)
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
        if self.life is None:
            self.logger.error("bot 尚未运行，无需停止")
            exit(0)
        self.life.cancel()
        await self.life

