import sys

import better_exceptions
from better_exceptions import ExceptionFormatter

# 修复在 windows powershell 显示错误的 bug
better_exceptions.encoding.ENCODING = sys.stdout.encoding
better_exceptions.formatter.ENCODING = sys.stdout.encoding
better_exceptions.hook()


class BotException(Exception):
    """Bot 异常基类

    在使用 melobot 编写代码时，若需要抛出异常，可以有意抛出该类。
    表明这是你设计的异常情况，而不是完全预期之外的异常。
    """

    def __init__(self, msg: str):
        super().__init__(self, msg)
        self.err = msg

    def __str__(self):
        return self.err


class BotValueError(BotException):
    def __init__(self, msg: str):
        super().__init__(msg)


class BotRuntimeError(BotException):
    def __init__(self, msg: str):
        super().__init__(msg)


class BotPluginError(BotException):
    def __init__(self, msg: str):
        super().__init__(msg)


class BotUtilsError(BotException):
    def __init__(self, msg: str):
        super().__init__(msg)


class BotIpcError(BotException):
    def __init__(self, msg: str):
        super().__init__(msg)


class BotSessionError(BotException):
    def __init__(self, msg: str):
        super().__init__(msg)


class BotSessionTimeout(BotException):
    """会话暂停的超时异常"""

    def __init__(self, msg: str = ""):
        super().__init__(msg)


class BotToolsError(BotException):
    def __init__(self, msg: str):
        super().__init__(msg)


class FuncSafeExited(BotException):
    def __init__(self, msg: str = ""):
        super().__init__(msg)


_EXC_FORMATTER = ExceptionFormatter(colored=False)


def get_better_exc(e: Exception) -> str:
    """返回生成更好的异常字符串"""
    return "".join(
        _EXC_FORMATTER.format_exception(e.__class__, e, sys.exc_info()[2])
    ).strip("\n")
