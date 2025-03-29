from typing_extensions import Any


class BotException(Exception):
    """bot 异常基类"""

    def __init__(self, *args: object):
        super().__init__(self, args)
        if not len(args):
            self.err = ""
        elif len(args) == 1:
            self.err = str(args[0])
        else:
            self.err = str(args)
        self.pretty_err = f"[{self.__class__.__module__}.{self.__class__.__qualname__}] {self.err}"

    def __str__(self) -> str:
        return self.err


class UtilError(BotException):
    """melobot.utils 异常"""


class UtilValidateError(UtilError):
    """:py:mod:`melobot.utils` 函数参数验证异常"""


class BotError(BotException):
    """melobot bot 异常"""


class SourceError(BotException):
    """melobot 源异常"""


class PluginError(BotException):
    """melobot 插件异常"""


class PluginAutoGenError(PluginError):
    """melobot 插件自动生成异常"""


class PluginLoadError(PluginError):
    """melobot 插件加载异常"""


class PluginIpcError(PluginError):
    """melobot 插件间通信异常"""


class SessionError(BotException):
    """melobot 会话异常"""


class SessionStateFailed(SessionError):
    def __init__(self, cur_state: str, meth: str) -> None:
        self.cur_state = cur_state
        super().__init__(f"当前会话状态 {cur_state} 不支持的操作：{meth}")


class SessionRuleLacked(SessionError): ...


class FlowError(BotException):
    """melobot 处理流异常"""


class LogError(BotException):
    """melobot 日志器异常"""


class HookError(BotException):
    """melobot 生命周期组件异常"""


class AdapterError(BotException):
    """melobot 适配器异常"""


class DependError(BotException):
    """melobot 依赖注入异常"""


class DependInitError(DependError):
    """melobot 依赖注入项初始化失败"""


class DependBindError(DependError):
    """melobot 依赖注入项值绑定失败"""


class DynamicImpError(BotException):
    """melobot 动态导入组件异常"""

    def __init__(self, *args: Any, name: str | None = None, path: str | None = None) -> None:
        super().__init__(self, *args)
        self.name = name
        self.path = path


class DynamicImpSpecEmpty(DynamicImpError):
    """melobot 动态导入时，模块的 spec 为空"""
