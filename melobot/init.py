import asyncio as aio
import os
import sys
from logging import Logger

from .core.dispatcher import BotDispatcher
from .core.linker import BotLinker
from .core.responder import BotResponder
from .interface.core import IBot, IMetaDispatcher
from .interface.plugins import IBotPlugin
from .interface.typing import *
from .models.event import MetaEvent
from .models.exceptions import *
from .plugins.handler import (MsgEventHandler, NoticeEventHandler,
                              ReqEventHandler)
from .plugins.plugin import PluginLoader
from .utils.config import BotConfig
from .utils.logger import generate_logger


class MetaEventHandler(IMetaDispatcher):
    def __init__(self) -> None:
        super().__init__()

    async def dispatch(self, metaEvent: MetaEvent) -> None:
        return await super().dispatch(metaEvent)


class RuntimeInfo:
    def __init__(self) -> None:
        self.version = '2.0.0-Beta1'
        self.proj_name = 'MeloBot'
        self.proj_url = 'https://github.com/AiCorein/Qbot-MeloBot'
        self.platform = sys.platform
        self.os_sep = os.sep
        self.os_pathsep = os.pathsep


class BotDaemon:
    """
    bot 守护模块，负责 bot 的启动、管理和关闭
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
        self._plugins: List[IBotPlugin]=[]
        self._loader = PluginLoader

    def init(self, config_dir) -> None:
        if self.__init_flag__:
            raise BotException("bot 对象不能重复初始化")
        
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
        self._plugins.append(plugin)
        self.logger.info(f"成功加载插件：{plugin.name}")

    def _bind_handlers(self, dispatcher: BotDispatcher, plugins: List[IBotPlugin]) -> None:
        msg_handlers, req_handlers, notice_handlers = [], [], []
        for plugin in plugins:
            for handler in plugin.handlers:
                if isinstance(handler, MsgEventHandler):
                    msg_handlers.append(handler)
                elif isinstance(handler, ReqEventHandler):
                    req_handlers.append(handler)
                elif isinstance(handler, NoticeEventHandler):
                    notice_handlers.append(handler)
        
        if len(msg_handlers) == 0:
            self.logger.warning("bot 核心没有可用的 message 执行方法")
        if len(req_handlers) == 0:
            self.logger.warning("bot 核心没有可用的 request 执行方法")
        if len(notice_handlers) == 0:
            self.logger.warning("bot 核心没有可用的 notice 执行方法")
        
        dispatcher.bind(msg_handlers, req_handlers, notice_handlers)

    async def _run(self) -> None:
        if not self.__init_flag__:
            raise BotException("必须先初始化才能启动")
        
        self._bind_handlers(self._dispatcher, self._plugins)
        self._responder.bind(self._linker)
        self._linker.bind(self._dispatcher, self._responder, self._meta_handler)
        
        async with self._linker:
            self._work = aio.create_task(self._linker.recv_routine())
            await self._work
    
    def run(self) -> None:
        try:
            aio.run(self._run())
        except KeyboardInterrupt:
            self.logger.info("监听到键盘中断，bot 即将停止工作")

    async def close(self) -> None:
        self._work.cancel()
        await self._work


melobot = BotDaemon()
