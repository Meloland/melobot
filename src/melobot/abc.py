from .typing import Any


class ReadOnly(type):
    def __new__(cls, name: str, bases: tuple[type, ...], dic: dict[str, Any]):
        _class = super().__new__(cls, name, bases, dic)
        super().__setattr__(
            _class,
            "__cvars__",
            tuple(k for k in dic if not k.startswith("__")),
        )
        return _class

    def __setattr__(self, name: str, value: Any) -> None:
        if name in getattr(self, "__cvars__"):
            raise AttributeError(f"{self.__name__} 类的类属性 {name} 是只读的，无法修改")
        return super().__setattr__(name, value)

    def __instance_setattr(self, name: str, value: Any) -> None:
        if hasattr(self, name):
            _class = self.__class__.__name__
            raise AttributeError(f"{_class} 类的实例属性 {name} 已有初始值，无法修改")
        super(self.__class__, self).__setattr__(name, value)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        setattr(self, "__setattr__", ReadOnly.__instance_setattr)
        return super().__call__(*args, **kwargs)
