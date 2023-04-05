class Singleton:
    def __new__(cls, *args, **kwargs) -> "Singleton":
        if not hasattr(cls, '__instance__'):
            cls.__instance__ = super(Singleton, cls).__new__(cls)
        return cls.__instance__