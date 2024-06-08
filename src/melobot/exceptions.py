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
    """Bot 异常基类

    在使用 melobot 编写代码时，若需要抛出异常，可以有意抛出该类。
    表明这是你设计的异常情况，而不是完全预期之外的异常。
    """

    def __init__(self, text: str):
        super().__init__(self, text)
        self.err = text

    def __str__(self):
        return self.err


class BotValidateError(BotException):
    def __init__(self, text: str):
        super().__init__(text)


class BotValueError(BotException):
    def __init__(self, text: str):
        super().__init__(text)


class BotRuntimeError(BotException):
    def __init__(self, text: str):
        super().__init__(text)


class BotPluginError(BotException):
    def __init__(self, text: str):
        super().__init__(text)


class BotUtilsError(BotException):
    def __init__(self, text: str):
        super().__init__(text)


class BotIpcError(BotException):
    def __init__(self, text: str):
        super().__init__(text)


class BotSessionError(BotException):
    def __init__(self, text: str):
        super().__init__(text)


class BotSessionTimeout(BotException):
    """会话暂停的超时异常"""

    def __init__(self, text: str = ""):
        super().__init__(text)


class FuncSafeExited(BotException):
    def __init__(self, text: str = ""):
        super().__init__(text)
