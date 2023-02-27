__all__ = [
    'Singleton'
]


class Singleton:
    """
    单例类
    """
    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '__instance__'):
            cls.__instance__ = super(Singleton, cls).__new__(cls)
        return cls.__instance__