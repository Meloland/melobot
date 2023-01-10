__all__ = [
    'Singleton'
]


class Singleton:
    """
    单例类
    """
    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            cls._instance = super(Singleton, cls).__new__(cls)
        return cls._instance