__all__ = [
    'BotException', 
    'BotWrongCmdFlag', 
    'BotUnknownEvent', 
    'BotUnexpectedEvent',
    'BotCmdExecFailed', 
    'BotUnknownCmd', 
    'BotUnexpectedFormat',
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


class BotUnexpectedEvent(BotException):
    def __init__(self, err: str):
        super().__init__(err)


class BotCmdExecFailed(BotException):
    def __init__(self, err: str):
        super().__init__(err)


class BotUnknownCmd(BotException):
    def __init__(self, err: str):
        super().__init__(err)


class BotUnexpectedFormat(BotException):
    def __init__(self, err: str):
        super().__init__(err)
