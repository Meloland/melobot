__all__ = [
    'Singleton',
    'Reflector'
]


class Singleton:
    """
    单例类
    """
    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '__instance__'):
            cls.__instance__ = super(Singleton, cls).__new__(cls)
        return cls.__instance__


class Reflector(Singleton):
    """
    通过反射获取值
    """
    def __init__(self) -> None:
        super().__init__()

    @classmethod
    def get(cls, obj: object, attrs: tuple) -> object:
        """
        反射获取
        """
        val = obj
        for attr in attrs: val = getattr(val, attr)
        return val
    
    @classmethod
    def set(cls, obj: object, attrs: tuple, val: object) -> None:
        """
        反射设置
        """
        field = obj
        for attr in attrs[:-1]: field = getattr(field, attr)
        setattr(field, attrs[-1], val)