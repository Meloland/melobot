import io
import sys

from better_exceptions import ExceptionFormatter
from rich import print


class BotException(Exception):
    """
    bot 异常基类
    """

    def __init__(self, msg: str):
        super().__init__(self, msg)
        self.err = msg

    def __str__(self):
        return self.err


class PluginLoadError(BotException):
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


class DirectRetSignal(BotException):
    def __init__(self, msg: str = ""):
        super().__init__(msg)


class SessionHupTimeout(BotException):
    def __init__(self, msg: str = ""):
        super().__init__(msg)


_EXC_FORMATTER = ExceptionFormatter(colored=False, pipe_char="|", cap_char="└")


def get_better_exc(e: Exception) -> str:
    """
    返回生成更好的异常字符串
    """
    return "".join(
        _EXC_FORMATTER.format_exception(e.__class__, e, sys.exc_info()[2])
    ).strip("\n")


def get_rich_locals(locals: dict) -> str:
    """
    返回使用 rich 格式化的 locals() dict
    """
    sio = io.StringIO()
    print(locals, file=sio)
    return sio.getvalue().strip("\n")
