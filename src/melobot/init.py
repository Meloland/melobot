import asyncio as aio
import inspect
import os
import sys

import better_exceptions

# 修复在 windows powershell 显示错误的 bug
better_exceptions.encoding.ENCODING = sys.stdout.encoding
better_exceptions.formatter.ENCODING = sys.stdout.encoding
better_exceptions.hook()

from .context.session import BotSessionManager
from .controller.dispatcher import BotDispatcher
from .controller.responder import BotResponder
from .io.forward_ws import ForwardWsConn
from .meta import (
    EXIT_CLOSE,
    EXIT_RESTART,
    MELOBOT_LOGO,
    MODULE_MODE_FLAG,
    MODULE_MODE_SET,
    MetaInfo,
)
from .models.event import BotEventBuilder
from .plugin.bot import BOT_PROXY, BotHookBus
from .plugin.handler import EVENT_HANDLER_MAP
from .plugin.ipc import PluginBus, PluginStore
from .plugin.plugin import Plugin, PluginLoader
from .types.exceptions import *
from .types.tools import get_rich_str
from .types.typing import *
from .utils.config import BotConfig
from .utils.logger import get_logger

if TYPE_CHECKING:
    from .utils.logger import Logger

if sys.platform != "win32":
    import uvloop

    aio.set_event_loop_policy(uvloop.EventLoopPolicy())


class MeloBot:
    """MeloBot 类。负责 bot 的启动、加载和管理。"""

    def __init__(self) -> None:
        #: bot 配置项
        self._config: BotConfig
        #: bot 元信息
        self._info: "MetaInfo" = MetaInfo()
        self.__logger: "Logger" = None

        self._life: aio.Task = None
        self._plugins: Dict[str, Plugin] = {}
        self._loader = PluginLoader

        self._linker: ForwardWsConn
        self._responder: BotResponder
        self._dispatcher: BotDispatcher
        self._ctx_manager = BotSessionManager
        self._event_builder = BotEventBuilder
        self._plugin_bus = PluginBus
        self._plugin_store = PluginStore
        self._bot_bus = BotHookBus
        self._proxy = BOT_PROXY

        self.__init_flag__ = False
        self._exit_code = EXIT_CLOSE

    @property
    def loop(self) -> aio.AbstractEventLoop:
        """获得运行 bot 的事件循环

        :return: 事件循环对象
        :rtype: asyncio.AbstractEventLoop
        """
        return aio.get_running_loop()

    @property
    def slack(self) -> bool:
        return self._linker.slack

    @slack.setter
    def slack(self, value: bool) -> None:
        self._linker.slack = value

    @property
    def logger(self) -> "Logger":
        return self.__logger if self.__logger else get_logger()

    def init(self, config_dir) -> None:
        """
        为 bot 核心加载配置文件
        """
        if self.__init_flag__:
            self.logger.error("bot 不能重复初始化")
            sys.exit(self._exit_code)

        for l in MELOBOT_LOGO.split("\n"):
            self.logger.info(l)
        self.logger.info(" 欢迎使用 melobot v2")
        self.logger.info(f" melobot 在 AGPL3 协议下开源发行")

        self._config = BotConfig(config_dir)
        self.__logger = get_logger(self._config.log_dir_path, self._config.log_level)
        # 在此之前日志会自动过滤到 INFO 级别
        self.logger.info("-" * 38)
        self.logger.info(f"运行版本：{self._info.VER}，平台：{self._info.PLATFORM}")
        self.logger.debug("配置已初始化：\n" + get_rich_str(self._config.__dict__))
        self.logger.debug(
            f"日志器参数如下，日志文件路径：{self._config.log_dir_path}，日志等级：{self._config.log_level}"
        )
        self._linker = ForwardWsConn(
            self._config.connect_host,
            self._config.connect_port,
            self._config.max_conn_try,
            self._config.conn_try_interval,
            self._config.cooldown_time,
            self._event_builder,
            self._bot_bus,
            self.logger,
        )
        self._responder = BotResponder(self.logger)
        self._dispatcher = BotDispatcher(
            EVENT_HANDLER_MAP, self._bot_bus, self._ctx_manager, self.logger
        )
        self._ctx_manager._bind(self._responder)
        self._plugin_bus._bind(self.logger)
        self._bot_bus._bind(self.logger)

        if os.environ.get(MODULE_MODE_FLAG) == MODULE_MODE_SET:
            self.logger.info("当前运行模式：模块运行模式")
        else:
            self.logger.info("当前运行模式：脚本运行模式")
        self.logger.debug("bot 核心初始化完成")
        self.__init_flag__ = True

    def load_plugin(self, plugin_target: str | Type[Plugin]) -> None:
        """
        为 bot 加载运行插件。支持传入插件起始目录字符串（绝对路径）或插件类
        """
        if not self.__init_flag__:
            self.logger.error("加载插件必须在初始化之后进行")
            sys.exit(self._exit_code)

        plugin_dir = (
            inspect.getfile(plugin_target)
            if not isinstance(plugin_target, str)
            else plugin_target
        )
        self.logger.debug(f"尝试加载来自 {plugin_dir} 的插件")
        plugin = self._loader.load(plugin_target, self.logger, self._responder)
        exist_plugin = self._plugins.get(plugin.ID)
        if exist_plugin is None:
            self._plugins[plugin.ID] = plugin
            self._dispatcher.add_handlers(plugin._handlers)
            self.logger.info(f"成功加载插件：{plugin.ID}")
        else:
            self.logger.error(
                f"加载插件出错：插件名称重复, 尝试加载：{plugin_dir}，已加载：{exist_plugin.plugin_dir}"
            )
            sys.exit(self._exit_code)

    def load_plugins(self, plugins_dir: str) -> None:
        """从插件目录批量加载插件

        :param plugins_dir: 插件包的目录
        :type plugins_dir: str
        """
        self.logger.debug(f"尝试从目录 {plugins_dir} 批量加载插件")
        items = os.listdir(plugins_dir)
        for item in items:
            path = os.path.join(plugins_dir, item)
            if os.path.isdir(path) and os.path.basename(path) != "__pycache__":
                self.load_plugin(path)

    async def _run(self) -> None:
        if len(self._plugins) == 0:
            self.logger.warning("没有加载任何插件，bot 将不会有任何操作")

        await self._bot_bus.emit(BotLife.LOADED)
        self.logger.debug("LOADED hook 已完成")
        self._responder.bind(self._linker)
        self._linker.bind(self._dispatcher, self._responder)
        self.logger.debug("各核心组件已完成绑定，准备启动连接支配器")
        try:
            async with self._linker:
                aio.create_task(self._linker.send_queue_watch())
                self._life = aio.create_task(self._linker.listen())
                self._proxy._bind(self)
                self.logger.info("bot 开始正常运行")
                await self._life
        except Exception as e:
            self.logger.error(f"bot 核心无法继续运行。异常：{e}")
            self.logger.error("异常回溯栈：\n" + get_better_exc(e))
            self.logger.error("异常点局部变量：\n" + get_rich_str(locals()))
        finally:
            await self._bot_bus.emit(BotLife.BEFORE_STOP, wait=True)
            self.logger.debug("BEFORE_STOP hook 已完成")
            self.logger.info("bot 已清理运行时资源")
            sys.exit(self._exit_code)

    def run(self) -> None:
        """
        运行 bot
        """
        if not self.__init_flag__:
            self.logger.error("必须先初始化才能启动")
            sys.exit(self._exit_code)
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
        if self._life is None:
            self.logger.error("bot 尚未运行，无需停止")
            sys.exit(self._exit_code)
        await self._bot_bus.emit(BotLife.BEFORE_CLOSE, wait=True)
        self.logger.debug("BEFORE_CLOSE hook 已完成")
        self._life.cancel()

    async def restart(self) -> None:
        """
        重启 bot
        """
        if self._life is None:
            self.logger.error("bot 尚未运行，无需重启")
            sys.exit(self._exit_code)
        if os.environ.get(MODULE_MODE_FLAG) != MODULE_MODE_SET:
            self.logger.error("只有在模块运行模式下，才能使用 bot 重启功能")
            return
        self.logger.info("bot 即将进行重新启动...")
        self._exit_code = EXIT_RESTART
        self._life.cancel()
