import sys

from better_exceptions import ExceptionFormatter


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


class DuplicateError(BotException):
    def __init__(self, msg: str):
        super().__init__(msg)


class BotValueError(BotException):
    def __init__(self, msg: str):
        super().__init__(msg)


class BotRuntimeError(BotException):
    def __init__(self, msg: str):
        super().__init__(msg)


class PluginInitError(BotException):
    def __init__(self, msg: str):
        super().__init__(msg)


class PluginBuildError(BotException):
    def __init__(self, msg: str):
        super().__init__(msg)


class BotConnectFailed(BotException):
    def __init__(self, msg: str):
        super().__init__(msg)


class BotHookError(BotException):
    def __init__(self, msg: str):
        super().__init__(msg)


class EventHandlerError(BotException):
    def __init__(self, msg: str):
        super().__init__(msg)


class BotCheckerError(BotException):
    def __init__(self, msg: str):
        super().__init__(msg)


class BotMatcherError(BotException):
    def __init__(self, msg: str):
        super().__init__(msg)


class TryFlagFailed(BotException):
    def __init__(self, msg: str):
        super().__init__(msg)


class ShareObjError(BotException):
    def __init__(self, msg: str):
        super().__init__(msg)


class PluginSignalError(BotException):
    def __init__(self, msg: str):
        super().__init__(msg)


class BotActionError(BotException):
    def __init__(self, msg: str):
        super().__init__(msg)


class BotSessionError(BotException):
    def __init__(self, msg: str):
        super().__init__(msg)


class BotBaseUtilsError(BotException):
    def __init__(self, msg: str):
        super().__init__(msg)


class ArgParseError(BotException):
    def __init__(self, msg: str):
        super().__init__(msg)


class ArgFormatInitError(BotException):
    def __init__(self, msg: str):
        super().__init__(msg)


class ArgVerifyFailed(BotException):
    def __init__(self, msg: str = ""):
        super().__init__(msg)


class ArgLackError(BotException):
    def __init__(self, msg: str = ""):
        super().__init__(msg)


class FuncSafeExited(BotException):
    def __init__(self, msg: str = ""):
        super().__init__(msg)


class SessionHupTimeout(BotException):
    """会话暂停的超时异常"""

    def __init__(self, msg: str = ""):
        super().__init__(msg)


_EXC_FORMATTER = ExceptionFormatter(colored=False)


def get_better_exc(e: Exception) -> str:
    """返回生成更好的异常字符串"""
    return "".join(
        _EXC_FORMATTER.format_exception(e.__class__, e, sys.exc_info()[2])
    ).strip("\n")
