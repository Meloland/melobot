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


class ArgFormatFailed(BotException):
    """
    专指格式化器格式化失败
    """

    def __init__(self, msg: str):
        super().__init__(msg)


class ArgVerifyFailed(BotException):
    """
    格式化时参数验证不通过
    """

    def __init__(self, msg: str = ""):
        super().__init__(msg)


class ArgLackError(BotException):
    """
    格式化时参数缺失
    """

    def __init__(self, msg: str = ""):
        super().__init__(msg)


class DirectRetSignal(BotException):
    """
    嵌套函数中快速 return 的信号，上游捕获后无视即可
    """

    def __init__(self, msg: str = ""):
        super().__init__(msg)


class SessionHupTimeout(BotException):
    """
    等待 session 被唤醒时的超时异常
    """

    def __init__(self, msg: str = ""):
        super().__init__(msg)
