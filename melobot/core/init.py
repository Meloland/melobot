import asyncio as aio
import importlib.util
import importlib.machinery
import inspect
import os
import pathlib
import sys
import traceback

import websockets.exceptions as wse

from ..interface.core import IActionResponder, IMetaDispatcher
from ..interface.exceptions import *
from ..interface.models import BotLife
from ..interface.typing import *
from ..interface.utils import Logger
from ..models.bot import BOT_PROXY, BotHookBus
from ..models.event import MetaEvent
from ..models.ipc import PluginBus, PluginStore
from ..models.plugin import Plugin
from ..utils.config import BotConfig
from ..utils.logger import get_logger
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
    """
    插件加载器
    """
    @classmethod
    def load_from_dir(cls, path: str) -> Plugin:
        """
        从指定插件目录加载插件
        """
        if not os.path.exists(os.path.join(path, '__init__.py')):
            raise BotRuntimeError("缺乏入口主文件 __init__.py，插件无法加载")
        init_path = str(pathlib.Path(path, '__init__.py').resolve(strict=True))
        package_name = os.path.basename(path)
        sys.path.append(str(pathlib.Path(path).parent.resolve(strict=True)))
        spec = importlib.util.spec_from_file_location(package_name, init_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        plugin_class = None
        for obj in module.__dict__.values():
            if isinstance(obj, type) and issubclass(obj, Plugin) and obj.__name__ != Plugin.__name__:
                plugin_class = obj
                break
        if plugin_class is None:
            raise BotRuntimeError("指定的入口主文件中，未发现继承 Plugin 的插件类，无法加载插件")
        plugin = plugin_class()
        dir = inspect.getfile(module)
        return (plugin, dir)

    @classmethod
    def load_from_type(cls, _class: Type[Plugin]) -> Plugin:
        """
        从插件类对象加载插件
        """
        plugin = _class()
        dir = inspect.getfile(_class)
        return (plugin, dir)

    @classmethod
    def load_plugin(cls, target: Union[str, Type[Plugin]], logger: Logger, responder: IActionResponder) -> Plugin:
        """
        加载插件
        """
        if isinstance(target, str):
            plugin, dir = cls.load_from_dir(target)
        else:
            plugin, dir = cls.load_from_type(target)
        root_path = pathlib.Path(dir).resolve(strict=True)
        plugin._Plugin__build(root_path, logger, responder)
        return plugin


class MeloBot:
    """
    bot 模块。负责整个 bot 的启动、加载和管理
    """
    def __init__(self) -> None:
        self.config: BotConfig
        self.info = METAINFO
        # 不要更改这个属性名
        self._logger: Logger=None

        self.life: aio.Task=None
        self.plugins: Dict[str, Plugin]={}
        self.loader = PluginLoader

        self.linker: BotLinker
        self.responder: BotResponder
        self.dispatcher: BotDispatcher
        self.meta_dispatcher = MetaEventDispatcher()
        self.plugin_bus = PluginBus
        self.plugin_store = PluginStore
        self.bot_bus = BotHookBus
        self.proxy = BOT_PROXY

        self.__init_flag__ = False

    @property
    def logger(self) -> Logger:
        return self._logger if self._logger else get_logger()

    def init(self, config_dir) -> None:
        """
        为 bot 核心加载配置文件
        """
        if self.__init_flag__:
            self.logger.error("bot 不能重复初始化")
            exit(0)
        
        self.config = BotConfig(config_dir)
        self._logger = get_logger(self.config.log_dir_path, self.config.log_level)
        self.linker = BotLinker(self.config.connect_host, self.config.connect_port, self.config.cooldown_time,
                                self.logger)
        self.responder = BotResponder(self.logger)
        self.dispatcher = BotDispatcher(self.logger)
        self.plugin_bus._bind(self.logger, self.responder)
        self.bot_bus._bind(self.logger, self.responder)

        self.logger.info("欢迎使用 melobot v2")
        self.logger.info(f"本项目在 AGPL3 协议下开源发行。更多请参阅：{self.info.PROJ_SRC}")
        self.logger.info(f"运行版本：{self.info.VER}，平台：{self.info.PLATFORM}")
        self.logger.info("bot 核心初始化完成")
        self.__init_flag__ = True

    def load(self, target: Union[str, Type[Plugin]]) -> None:
        """
        为 bot 加载运行插件。支持传入插件起始目录字符串（绝对路径）或插件类
        """
        if not self.__init_flag__:
            self.logger.error("加载插件必须在初始化之后进行")
            exit(0)
        
        plugin_dir = inspect.getfile(target) if not isinstance(target, str) else target
        self.logger.debug(f"尝试加载来自 {plugin_dir} 的插件")
        plugin = self.loader.load_plugin(target, self.logger, self.responder)
        exist_plugin = self.plugins.get(plugin.__class__.__id__)
        if exist_plugin is None:
            self.plugins[plugin.__class__.__id__] = plugin
            self.dispatcher.add_handlers(plugin._Plugin__handlers)
            self.logger.info(f"成功加载插件：{plugin.__class__.__id__}")
        else:
            self.logger.error(f"加载插件出错：插件名称重复, 尝试加载：{plugin_dir}，已加载：{exist_plugin.plugin_dir}")
            exit(0)

    async def _run(self) -> None:
        if len(self.plugins) == 0:
            self.logger.warning("没有加载任何插件，bot 将不会有任何操作")

        await self.bot_bus.emit(BotLife.LOADED)
        self.responder.bind(self.linker)
        self.linker.bind(self.dispatcher, self.responder, self.meta_dispatcher)
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
            self.logger.debug('异常回溯栈：\n' + traceback.format_exc().strip('\n'))
        finally:
            await self.bot_bus.emit(BotLife.BEFORE_STOP, wait=True)
            self.logger.info("bot 已清理运行时资源并关闭")
    
    def run(self) -> None:
        """
        运行 bot
        """
        if not self.__init_flag__:
            self.logger.error("必须先初始化才能启动")
            exit(0)
        try:
            """
            一定要使用 get_event_loop，在启动前部分核心模块里初始化 asyncio 中的对象，
            已经生成了事件循环，使用 asyncio.run 将会运行一个新的事件循环
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
            exit(0)
        await self.bot_bus.emit(BotLife.BEFORE_CLOSE, wait=True)
        self.life.cancel()
