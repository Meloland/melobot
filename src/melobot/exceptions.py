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
    def __init__(self, obj: object = ""):
        super().__init__(self, obj)
        self.err = str(obj)

    def __str__(self) -> str:
        return self.err


class ValidateError(BotException): ...


class BotError(BotException): ...


class IOError(BotException): ...


class PluginError(BotException): ...


class PluginIpcError(PluginError): ...


class SessionError(BotException): ...


class FlowError(BotException): ...


class LogError(BotException): ...


class HookError(BotException): ...


class AdapterError(BotException): ...


class DependError(BotException): ...


class DependInitError(DependError): ...


class DependBindError(DependError): ...
