__all__ = [
    'BotException', 
    'BotWrongCmdFlag', 
    'BotUnknownEvent', 
    'BotUnexpectEvent',
    'BotCmdExecFailed', 
    'BotUnknownCmdName', 
    'BotUnexpectFormat',
    'GetActiveSessionError'
]


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


class BotWrongCmdFlag(BotException):
    def __init__(self, err: str):
        super().__init__(err)


class BotUnknownEvent(BotException):
    def __init__(self, err: str):
        super().__init__(err)


class BotUnexpectEvent(BotException):
    def __init__(self, err: str):
        super().__init__(err)


class BotCmdExecFailed(BotException):
    def __init__(self, err: str):
        super().__init__(err)


class BotUnknownCmdName(BotException):
    def __init__(self, err: str):
        super().__init__(err)


class BotUnexpectFormat(BotException):
    def __init__(self, err: str):
        super().__init__(err)


class GetActiveSessionError(BotException):
    def __init__(self, err: str):
        super().__init__(err)