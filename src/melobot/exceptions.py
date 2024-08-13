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
logging._loggerClass = logging.Logger  # type:ignore[attr-defined]


class BotException(Exception):
    def __init__(self, obj: object):
        super().__init__(self, obj)
        self.err = str(obj)

    def __str__(self):
        return self.err


class BotValidateError(BotException):
    def __init__(self, obj: object):
        super().__init__(obj)


class BotRuntimeError(BotException):
    def __init__(self, obj: object):
        super().__init__(obj)


class BotPluginError(BotException):
    def __init__(self, obj: object):
        super().__init__(obj)


class BotIpcError(BotException):
    def __init__(self, obj: object):
        super().__init__(obj)


class BotSessionError(BotException):
    def __init__(self, obj: object):
        super().__init__(obj)


class ProcessFlowError(BotException):
    def __init__(self, obj: object):
        super().__init__(obj)


class BotLogError(BotException):
    def __init__(self, obj: object):
        super().__init__(obj)


class BotHookError(BotException):
    def __init__(self, obj: object):
        super().__init__(obj)


class BotAdapterError(BotException):
    def __init__(self, obj: object):
        super().__init__(obj)


class BotDependError(BotException):
    def __init__(self, obj: object):
        super().__init__(obj)
