import logging
import sys
from typing import Any

import better_exceptions

better_exceptions.SUPPORTS_COLOR = True
better_exceptions.color.SUPPORTS_COLOR = True
better_exceptions.formatter.SUPPORTS_COLOR = True
# 修复在 windows powershell 显示错误的 bug
better_exceptions.encoding.ENCODING = sys.stdout.encoding
better_exceptions.formatter.ENCODING = sys.stdout.encoding
# 直接 hook，而不是让它使用环境变量触发
sys.excepthook = better_exceptions.excepthook
# 取消它的猴子补丁
logging._loggerClass = (  # type:ignore[attr-defined]
    logging.Logger
)


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
        self.pretty_err = (
            f"[{self.__class__.__module__}.{self.__class__.__qualname__}] {self.err}"
        )

    def __str__(self) -> str:
        return self.err


class ValidateError(BotException):
    """:py:mod:`melobot.utils` 函数参数验证异常"""


class BotError(BotException):
    """melobot bot 异常"""


class IOError(BotException):
    """melobot 输入输出源异常"""


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


class DynamicImpError(BotException, ImportError):
    """melobot 动态导入组件异常"""

    def __init__(
        self, *args: Any, name: str | None = None, path: str | None = None
    ) -> None:
        BotException.__init__(self, *args)
        ImportError.__init__(self, *args, name=name, path=path)
