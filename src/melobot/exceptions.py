import logging
import sys

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
logging._loggerClass = (  # type:ignore[attr-defined] # pylint: disable=protected-access
    logging.Logger
)


class BotException(Exception):
    """bot 异常基类"""

    def __init__(self, obj: object = ""):
        super().__init__(self, obj)
        self.err = str(obj)

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


class DynamicImpError(BotException):
    """melobot 动态导入组件异常"""
