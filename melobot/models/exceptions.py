__all__ = (
    'BotException', 
    'BotUnexceptedObj', 
    'BotValueError', 
    'BotInvalidSession',
    'BotPluginDenied'
)


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


class BotUnexceptedObj(BotException):
    def __init__(self, err: str):
        super().__init__(err)


class BotValueError(BotException):
    def __init__(self, err: str):
        super().__init__(err)


class BotInvalidSession(BotException):
    def __init__(self, err: str):
        super().__init__(err)


class BotPluginDenied(BotException):
    def __init__(self, err: str):
        super().__init__(err)