import inspect
from copy import deepcopy

from .exceptions import BotValueError
from .typing import Any


class ReadOnlyMeta(type):
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
        setattr(self, "__setattr__", ReadOnlyMeta.__instance_setattr)
        return super().__call__(*args, **kwargs)


class MarkableMixin:
    def __init__(self) -> None:
        self._flags: dict[str, dict[str, Any]] = {}

    def flag_mark(self, namespace: str, flag_name: str, val: Any = None) -> None:
        self._flags.setdefault(namespace, {})

        if flag_name in self._flags[namespace].keys():
            raise BotValueError(
                f"标记失败。对象的命名空间 {namespace} 中已存在名为 {flag_name} 的标记"
            )

        self._flags[namespace][flag_name] = val

    def flag_check(self, namespace: str, flag_name: str, val: Any = None) -> bool:
        if self._flags.get(namespace) is None:
            return False
        if flag_name not in self._flags[namespace].keys():
            return False
        flag = self._flags[namespace][flag_name]
        return flag is val if val is None else flag == val


class ClonableMixin:
    def copy(self):
        return deepcopy(self)


class AttrsReprMixin:
    def __repr__(self) -> str:
        attrs = ", ".join(
            f"{k}={repr(v)}" for k, v in self.__dict__.items() if not k.startswith("_")
        )
        return f"{self.__class__.__name__}({attrs})"


class LocatableMixin:
    def __new__(cls, *_args, **_kwargs):
        obj = super().__new__(cls)
        setattr(obj, "__obj_location__", obj._init_location())
        return obj

    @staticmethod
    def _init_location():
        frame = inspect.currentframe()
        while frame:
            if frame.f_code.co_name == "<module>":
                return {
                    "module": frame.f_globals["__name__"],
                    "file": frame.f_globals["__file__"],
                    "line": frame.f_lineno,
                }
            frame = frame.f_back

    @property
    def __obj_module__(self) -> str:
        return getattr(self, "__obj_location__")["module"]

    @property
    def __obj_file__(self) -> str:
        return getattr(self, "__obj_location__")["file"]

    @property
    def __obj_line__(self) -> int:
        return getattr(self, "__obj_location__")["line"]
