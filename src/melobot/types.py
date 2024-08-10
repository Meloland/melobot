import inspect
from abc import ABCMeta, abstractmethod
from copy import deepcopy
from enum import Enum
from os import PathLike
from types import ModuleType, TracebackType
from typing import *

from typing_extensions import Self


class MarkableMixin:
    def __init__(self) -> None:
        self._flags: dict[str, dict[str, Any]] = {}

    def flag_mark(self, namespace: str, flag_name: str, val: Any = None) -> None:
        self._flags.setdefault(namespace, {})

        if flag_name in self._flags[namespace].keys():
            raise ValueError(
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


class HandleLevel(float, Enum):
    """事件处理器优先级枚举类型"""

    MAX = 1 << 6
    ULTRA_HIGH = 1 << 5
    HIGH = 1 << 4
    NORMAL = 1 << 3
    LOW = 1 << 2
    ULTRA_LOW = 1 << 1
    MIN = 1


class LogicMode(Enum):
    """逻辑模式枚举类型"""

    AND = 1
    OR = 2
    NOT = 3
    XOR = 4

    @classmethod
    def calc(cls, logic: "LogicMode", v1: Any, v2: Any = None) -> bool:
        if logic == LogicMode.AND:
            return (v1 and v2) if v2 is not None else bool(v1)
        elif logic == LogicMode.OR:
            return (v1 or v2) if v2 is not None else bool(v1)
        elif logic == LogicMode.NOT:
            return not v1
        elif logic == LogicMode.XOR:
            return (v1 ^ v2) if v2 is not None else bool(v1)

    @classmethod
    def seq_calc(cls, logic: "LogicMode", values: list[Any]) -> bool:
        if len(values) <= 0:
            return False
        elif len(values) <= 1:
            return bool(values[0])

        idx = 0
        res: bool
        while idx < len(values):
            if idx == 0:
                res = cls.calc(logic, values[idx], values[idx + 1])
                idx += 1
            else:
                res = cls.calc(logic, res, values[idx])
            idx += 1
        return res


#: 泛型 T，无约束
T = TypeVar("T")
#: :obj:`typing.ParamSpec` 泛型 P，无约束
P = ParamSpec("P")
#: 参数为 P，返回 Awaitable[T] 的可调用对象
AsyncCallable: TypeAlias = Callable[P, Awaitable[T]]


def abstractattr(obj: Callable[[Any], T] | None = None) -> T:
    _obj = cast(Any, obj)
    if obj is None:
        _obj = BetterABCMeta.DummyAttribute()
    _obj.__is_abstract_attribute__ = True
    return cast(T, _obj)


class BetterABCMeta(ABCMeta):

    class DummyAttribute: ...

    def __call__(cls, *args, **kwargs):
        instance = ABCMeta.__call__(cls, *args, **kwargs)
        lack_attrs = set()
        for name in dir(instance):
            attr = getattr(instance, name)
            if getattr(attr, "__is_abstract_attribute__", False):
                lack_attrs.add(name)
            if inspect.iscoroutine(attr):
                attr.close()
        if lack_attrs:
            raise NotImplementedError(
                "Can't instantiate abstract class {} with"
                " abstract attributes: {}".format(cls.__name__, ", ".join(lack_attrs))
            )
        return instance


class BetterABC(metaclass=BetterABCMeta):
    __slots__ = ()


class Placeholder(Enum):
    EMPTY = type("_Empty", (), {})
