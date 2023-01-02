class Singleton:
    """
    单例类
    """
    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            cls._instance = super(Singleton, cls).__new__(cls)
        return cls._instance


class BotEvent(dict):
    pass


class BotAction(dict):
    pass


class BotException(Exception):
    """
    bot 异常基类
    """
    def __init__(self, err: str):
        super().__init__(self)
        self.err = f'[{self.__class__.__name__}] {err}'
        self.origin_err = err
    
    def __str__(self):
        return self.err


class BotUnsupportCmdFlag(BotException):
    def __init__(self, err: str):
        super().__init__(err)


class BotUnknownEvent(BotException):
    def __init__(self, err: str):
        super().__init__(err)


class BotUnexpectedEvent(BotException):
    def __init__(self, err: str):
        super().__init__(err)


class BotCmdExecFailed(BotException):
    def __init__(self, err: str):
        super().__init__(err)


class BotUnknownCmdName(BotException):
    def __init__(self, err: str):
        super().__init__(err)