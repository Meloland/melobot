class BotException(Exception):
    """
    bot 异常基类
    """
    def __init__(self, msg: str):
        super().__init__(self, msg)
        self.err = msg
    
    def __str__(self):
        return self.err


class BotRuntimeError(BotException):
    """
    外部不符合运行逻辑的操作，引起的异常
    """
    def __init__(self, msg: str):
        super().__init__(msg)


class BotValueError(BotException):
    """
    值错误引起的异常
    """
    def __init__(self, msg: str):
        super().__init__(msg)


class BotTypeError(BotException):
    """
    类型错误引起的异常
    """
    def __init__(self, msg: str):
        super().__init__(msg)


class BotQuickExitSignal(BotException):
    """
    嵌套函数中快速 return 的信号，上游捕获后无视即可
    """
    def __init__(self, msg: str=""):
        super().__init__(msg)