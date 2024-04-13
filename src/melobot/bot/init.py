import asyncio
import os
from contextvars import ContextVar, Token

from ..base.abc import AbstractConnector, BaseLogger
from ..base.exceptions import BotRuntimeError, BotValueError
from ..base.typing import (
    TYPE_CHECKING,
    Any,
    BotLife,
    Coroutine,
    Literal,
    Optional,
    Void,
)
from ..context.session import SESSION_LOCAL, BotSessionManager
from ..controller.dispatcher import BotDispatcher
from ..controller.responder import BotResponder
from ..meta import MetaInfo
from ..models.event import BotEventBuilder
from ..plugin.handler import EVENT_HANDLER_MAP
from ..plugin.init import BotPlugin, PluginLoader, PluginProxy
from ..plugin.ipc import PluginBus, PluginStore
from ..utils.logger import BotLogger, NullLogger, log_exc
from .hook import BotHookBus

if TYPE_CHECKING:
    from ..plugin.ipc import ShareObject

if MetaInfo.PLATFORM not in ("win32", "cygwin", "cli"):
    import uvloop

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
else:
    import winloop

    asyncio.set_event_loop_policy(winloop.EventLoopPolicy())


def _safe_blocked_run(main: Coroutine[Any, Any, None]) -> None:
    try:
        asyncio.set_event_loop(asyncio.get_event_loop())
        asyncio.run(main)
    except KeyboardInterrupt:
        pass


class MeloBot:
    """bot 类。该类实例化即一个 bot 实例"""

    BOTS: dict[str, "MeloBot"] = {}

    def __init__(self, name: str) -> None:
        """初始化一个 bot 实例

        :param name: bot 实例的名字（唯一）
        """
        if name in MeloBot.BOTS.keys():
            raise BotValueError(f"命名为 {name} 的 bot 实例已存在，请改名避免冲突")
        MeloBot.BOTS[name] = self

        #: bot 的名字（唯一）
        self.name: str = name
        #: 元信息
        self.info: type[MetaInfo] = MetaInfo
        #: bot 的日志器
        self.logger: BaseLogger
        #: bot 的连接器
        self.connector: AbstractConnector

        self._plugins: dict[str, BotPlugin] = {}
        self._loader = PluginLoader
        self._ctx_manager = BotSessionManager
        self._event_builder = BotEventBuilder
        self._plugin_store = PluginStore()
        self._plugin_bus = PluginBus()
        self._bot_bus = BotHookBus()
        self._responder = BotResponder()
        self._dispatcher = BotDispatcher()
        self._life_ended = asyncio.Event()

        self.__init_flag__: bool = False
        self.__run_flag__: bool = False

    def init(
        self,
        connector: AbstractConnector,
        enable_log: bool = True,
        logger_name: Optional[str] = None,
        log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO",
        log_to_console: bool = True,
        log_to_dir: Optional[str] = None,
        log_tag: bool = False,
        custom_logger: Optional[BaseLogger] = None,
    ) -> "MeloBot":
        """初始化 bot 实例

        :param connector: 使 bot 实例工作的连接器
        :param enable_log: 是否启用日志
        :param logger_name: 日志器名称, 为空则使用 bot 实例名字
        :param log_level: 日志器日志等级
        :param log_to_console: 日志是否输出到控制台
        :param log_to_dir: 保存日志文件的目录，为空则不保存
        :param log_tag: 是否在日志中输出日志器名称，默认不输出
        :param custom_logger: 自定义日志器对象。若不为空将使用该日志器，并忽略其他所有日志相关参数
        :return: bot 实例（因此支持链式调用）
        """
        if connector._used:
            raise BotRuntimeError("bot 初始化时，不可使用已被其他 bot 实例使用的连接器")
        connector._used = True
        self.connector = connector

        if custom_logger is not None:
            self.logger = custom_logger
        elif not enable_log:
            self.logger = NullLogger(f"__MELOBOT_NULL_{self.name}__")
        else:
            self.logger = BotLogger(
                self.name if logger_name is None else logger_name,
                log_level,
                log_to_console,
                log_to_dir,
                not log_tag,
            )
        self.logger.debug(f"连接器已初始化，类型：{connector.__class__.__name__}")

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
        return self

    def load_plugin(self, plugin_target: str | BotPlugin) -> "MeloBot":
        """为 bot 实例加载插件

        :param plugin_target: 插件目标，可传入插件对象或插件包（一个插件即是一个 python package）的路径
        :return: bot 实例（因此支持链式调用）
        """
        if not self.__init_flag__:
            raise BotRuntimeError("bot 尚未初始化，不能加载插件")

        plugin_dir = None if not isinstance(plugin_target, str) else plugin_target
        if plugin_dir is None:
            self.logger.debug(f"尝试加载插件 {plugin_target}")
        else:
            self.logger.debug(f"尝试加载来自 {plugin_dir} 的插件")
        plugin = self._loader.load(plugin_target)
        exist_plugin = self._plugins.get(plugin.ID)
        if exist_plugin is not None:
            self.logger.error(
                f"加载插件出错：插件 id 重复, 重复的 id 为：{plugin.ID}，已取消该插件加载"
            )
            return self
        if not plugin.MULTI_USE and plugin._loaded_once:
            raise BotRuntimeError(
                f"插件 {plugin.ID} 不支持多 bot，但它已被其他 bot 加载"
            )
        plugin._loaded_once = True

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

        self._plugins[plugin.ID] = plugin
        self._dispatcher.add_handlers(handlers)
        self.logger.info(f"成功加载插件：{plugin.ID}")
        return self

    def load_plugins(self, plugins_dir: str) -> "MeloBot":
        """为 bot 实例批量加载插件

        :param plugins_dir: 传入包含所有插件包（一个插件即是一个 python package）的目录
        :return: bot 实例（因此支持链式调用）
        """
        if not self.__init_flag__:
            raise BotRuntimeError("bot 尚未初始化，不能加载插件")

        self.logger.debug(f"尝试从目录 {plugins_dir} 批量加载插件")
        items = os.listdir(plugins_dir)
        for item in items:
            path = os.path.join(plugins_dir, item)
            if os.path.isdir(path) and os.path.basename(path) != "__pycache__":
                self.load_plugin(path)
        return self

    async def _run(self) -> None:
        if not self.__init_flag__:
            raise BotRuntimeError("bot 尚未初始化，不能启动")
        if self.__run_flag__:
            raise BotRuntimeError("bot 已在运行，无需再次启动")
        if len(self._plugins) == 0:
            self.logger.warning("没有加载任何插件，bot 将不会有任何操作")

        self.logger.info(f"运行版本：{self.info.VER} | 平台：{self.info.PLATFORM}")
        bot_token = BOT_LOCAL._add_ctx(self)
        await self._bot_bus.emit(BotLife.LOADED)
        self.logger.debug("LOADED hook 已完成")
        try:
            async with self.connector:
                self._dispatcher._set_ready()
                self._responder._set_ready()
                self.connector._set_ready()
                self.__run_flag__ = True
                self.logger.info("bot 开始正常运行")
                self.logger.debug(
                    f"使用的连接器类型：{self.connector.__class__.__name__}"
                )
                await self._life_ended.wait()
        except Exception as e:
            self.logger.error(f"bot 核心无法继续运行。异常：{e}")
            log_exc(self.logger, locals(), e)
        finally:
            await self._bot_bus.emit(BotLife.BEFORE_STOP, wait=True)
            self.logger.debug("BEFORE_STOP hook 已完成")
            self.logger.info("bot 已清理运行时资源")
            BOT_LOCAL._del_ctx(bot_token)
            self.__run_flag__ = False

    def run(self) -> None:
        """运行 bot 实例"""
        _safe_blocked_run(self._run())

    async def close(self) -> None:
        """停止 bot 实例"""
        if not self.__run_flag__:
            raise BotRuntimeError("bot 尚未运行，无需停止")

        await self._bot_bus.emit(BotLife.BEFORE_CLOSE, wait=True)
        self.logger.debug("BEFORE_CLOSE hook 已完成")
        self._life_ended.set()

    def is_activate(self) -> bool:
        """判断 bot 实例是否在非 slack 状态

        slack 状态启用后仅会禁用行为操作的发送，无其他影响

        :return: 是否在非 slack 状态
        """
        if not self.__init_flag__:
            raise BotRuntimeError("bot 尚未初始化，不能执行此方法")

        return not self.connector.slack

    def activate(self) -> "MeloBot":
        """使 bot 实例退出 slack 状态

        slack 状态启用后仅会禁用行为操作的发送，无其他影响

        :return: bot 实例（因此支持链式调用）
        """
        if not self.__init_flag__:
            raise BotRuntimeError("bot 尚未初始化，不能执行此方法")

        self.connector.slack = False
        self.logger.debug("bot 已进入 activated 状态")
        return self

    def slack(self) -> "MeloBot":
        """使 bot 实例进入 slack 状态

        slack 状态启用后仅会禁用行为操作的发送，无其他影响

        :return: bot 实例（因此支持链式调用）
        """
        if not self.__init_flag__:
            raise BotRuntimeError("bot 尚未初始化，不能执行此方法")

        self.connector.slack = True
        self.logger.debug("bot 已进入 slack 状态")
        return self

    def get_plugins(self) -> dict[str, PluginProxy]:
        """获得 bot 实例所有插件的信息

        :return: 所有插件的信息
        """
        if not self.__init_flag__:
            raise BotRuntimeError("bot 尚未初始化，不能执行此方法")

        return {name: p.__proxy__ for name, p in self._plugins.items()}

    def emit_signal(
        self, namespace: str, signal: str, *args: Any, wait: bool = False, **kwargs: Any
    ) -> Any:
        """在本 bot 实例范围内发起一个信号

        :param namespace: 触发信号的命名空间
        :param signal: 触发信号的名字
        :param wait: 是否等待信号处理方法处理完毕
        :param args: 传递给信号处理方法的 args
        :param kwargs: 传递给信号处理方法的 kwargs
        :return: 不等待信号处理方法处理，只返回 :obj:`None`；若等待则返回运行结果
        """
        if not self.__init_flag__:
            raise BotRuntimeError("bot 尚未初始化，不能执行此方法")

        if self.logger.check_level_flag("DEBUG"):
            self.logger.debug(
                f"bot 信号触发：{namespace}.{signal} | wait: {wait}"
                f"（当前 session 上下文：{SESSION_LOCAL:hexid}），传递参数：args={args}, kwargs={kwargs}"
            )
        return self._plugin_bus.emit(namespace, signal, *args, wait=wait, **kwargs)

    def get_share(self, namespace: str, id: str) -> "ShareObject":
        """获得 bot 实例内的共享对象

        :param namespace: 共享对象的命名空间
        :param id: 共享对象的标识 id
        :return: 获得到的共享对象
        """
        if not self.__init_flag__:
            raise BotRuntimeError("bot 尚未初始化，不能执行此方法")

        self.logger.debug(
            f"获取共享对象行为：{namespace}.{id}（当前 session 上下文：{SESSION_LOCAL:hexid}）"
        )
        return self._plugin_store.get(namespace, id)

    @classmethod
    def start(cls, *bots: "MeloBot") -> None:
        """同时运行多个 bot 实例

        :param bots: 要运行的 bot 实例
        """

        async def bots_run():
            tasks = []
            for bot in bots:
                tasks.append(asyncio.create_task(bot._run()))
            try:
                await asyncio.wait(tasks)
            except asyncio.CancelledError:
                pass

        _safe_blocked_run(bots_run())

    @classmethod
    async def unicast(
        cls,
        target: str,
        namespace: str,
        signal: str,
        *args: Any,
        wait: bool = False,
        **kwargs: Any,
    ) -> None:
        """在指定的 bot 实例范围发起信号，即单播

        :param target: 单播的目标 bot 实例的名字
        :param namespace: 信号的命名空间
        :param signal: 信号的名字
        :param wait: 是否等待信号处理方法处理完毕
        :param args: 传递给信号处理方法的 args
        :param kwargs: 传递给信号处理方法的 kwargs
        """
        bot = cls.BOTS.get(target)
        if bot is None:
            raise BotValueError(f"单播指定的 bot 实例 {target} 不存在")

        b_token = BOT_LOCAL._add_ctx(bot)
        s_token = SESSION_LOCAL._add_ctx(Void)
        try:
            await bot.emit_signal(namespace, signal, *args, **kwargs, wait=wait)
        except AttributeError as e:
            if "Void" in e.__str__():
                raise BotRuntimeError(
                    "多播或单播时，bot 和 session 的上下文传递将会被阻隔。如需使用，请将它们作为参数显式传递"
                )
            else:
                raise e
        finally:
            BOT_LOCAL._del_ctx(b_token)
            SESSION_LOCAL._del_ctx(s_token)

    @classmethod
    async def multicast(
        cls,
        targets: list[str] | Literal["ALL"],
        namespace: str,
        signal: str,
        *args: Any,
        self_exclude: bool = True,
        wait: bool = False,
        **kwargs: Any,
    ) -> None:
        """在指定的多个 bot 实例范围发起信号，即多播

        :param targets: 多个 bot 实例的名字列表，为 "ALL" 时代表向所有 bot 多播，即广播
        :param namespace: 信号的命名空间
        :param signal: 信号的名字
        :param self_exclude: 是否在多播时排除自己
        :param wait: 是否等待信号处理方法处理完毕
        :param args: 传递给信号处理方法的 args
        :param kwargs: 传递给信号处理方法的 kwargs
        """
        if isinstance(targets, list):
            _targets = targets
        else:
            _targets = list(cls.BOTS.keys())
            if self_exclude:
                _targets.remove(BOT_LOCAL.name)
        tasks = []
        for name in _targets:
            tasks.append(
                asyncio.create_task(
                    cls.unicast(name, namespace, signal, *args, **kwargs, wait=wait)
                )
            )
        if len(tasks):
            await asyncio.wait(tasks)

    @classmethod
    def use_default_loop_policy(cls) -> None:
        """使用默认的事件循环策略

        在类 `Unix` 平台上，这会停止 `uvloop` 的使用

        在 `Windows` 平台上，这会停止 `winloop` 的使用
        """
        asyncio.set_event_loop_policy(None)


class BotLocal:
    """bot 实例自动上下文"""

    __slots__ = tuple(
        list(filter(lambda x: not (len(x) >= 2 and x[:2] == "__"), dir(MeloBot)))
        + ["__storage__"]
    )

    def __init__(self) -> None:
        object.__setattr__(self, "__storage__", ContextVar("melobot_ctx"))
        self.__storage__: ContextVar["MeloBot"]

    def __setattr__(self, __name: str, __value: Any) -> None:
        setattr(self.__storage__.get(), __name, __value)

    def __getattr__(self, __name: str) -> Any:
        return getattr(self.__storage__.get(), __name)

    def _add_ctx(self, ctx: "MeloBot") -> Token:
        return self.__storage__.set(ctx)

    def _del_ctx(self, token: Token) -> None:
        self.__storage__.reset(token)


BOT_LOCAL = BotLocal()
BotSessionManager._bind(BOT_LOCAL)
