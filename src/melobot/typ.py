import inspect
from abc import ABCMeta, abstractmethod
from enum import Enum
from typing import Any, Awaitable, Callable, ParamSpec, TypeAlias, TypeVar, cast

from beartype import BeartypeConf as _BeartypeConf
from beartype.door import is_bearable as _is_type
from beartype.door import is_subhint
from typing_extensions import TypeGuard

__all__ = (
    "T",
    "P",
    "AsyncCallable",
    "is_type",
    "is_subhint",
    "HandleLevel",
    "LogicMode",
    "BetterABCMeta",
    "BetterABC",
    "abstractattr",
    "abstractmethod",
    "VoidType",
)

T = TypeVar("T")
P = ParamSpec("P")
AsyncCallable: TypeAlias = Callable[P, Awaitable[T]]

_DEFAULT_BEARTYPE_CONF = _BeartypeConf(is_pep484_tower=True)


def is_type(obj: T, hint: type[Any]) -> TypeGuard[T]:
    ret = _is_type(obj, hint, conf=_DEFAULT_BEARTYPE_CONF)
    return ret


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
            return (v1 and v2) if v2 is not None else bool(v1)  # type: ignore[no-any-return]
        if logic == LogicMode.OR:
            return (v1 or v2) if v2 is not None else bool(v1)  # type: ignore[no-any-return]
        if logic == LogicMode.NOT:
            return not v1
        return (v1 ^ v2) if v2 is not None else bool(v1)  # type: ignore[no-any-return]

    @classmethod
    def short_calc(
        cls, logic: "LogicMode", v1: Callable[[], Any], v2: Callable[[], Any]
    ) -> bool:
        if logic == LogicMode.AND:
            return (v1() and v2()) if v2 is not None else bool(v1())  # type: ignore[no-any-return]
        if logic == LogicMode.OR:
            return (v1() or v2()) if v2 is not None else bool(v1())  # type: ignore[no-any-return]
        if logic == LogicMode.NOT:
            return not v1()
        return (v1() ^ v2()) if v2 is not None else bool(v1())  # type: ignore[no-any-return]

    @classmethod
    async def async_short_calc(
        cls, logic: "LogicMode", v1: AsyncCallable[[], Any], v2: AsyncCallable[[], Any]
    ) -> bool:

        if logic == LogicMode.AND:
            res = (await v1() and await v2()) if v2 is not None else bool(await v1())
            return res  # type: ignore[no-any-return]
        if logic == LogicMode.OR:
            res = (await v1() or await v2()) if v2 is not None else bool(await v1())
            return res  # type: ignore[no-any-return]
        if logic == LogicMode.NOT:
            return not await v1()
        res = (await v1() ^ await v2()) if v2 is not None else bool(await v1())
        return res  # type: ignore[no-any-return]

    @classmethod
    def seq_calc(cls, logic: "LogicMode", values: list[Any]) -> bool:
        if len(values) <= 0:
            return False
        if len(values) <= 1:
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

    @classmethod
    def short_seq_calc(cls, logic: "LogicMode", getters: list[Callable[[], Any]]) -> bool:
        if len(getters) <= 0:
            return False
        if len(getters) <= 1:
            return bool(getters[0]())

        idx = 0
        res: bool
        while idx < len(getters):
            if idx == 0:
                res = cls.short_calc(logic, getters[idx], getters[idx + 1])
                idx += 1
            else:
                res = cls.short_calc(logic, lambda: res, getters[idx])
            idx += 1
        return res

    @classmethod
    async def async_short_seq_calc(
        cls, logic: "LogicMode", getters: list[AsyncCallable[[], Any]]
    ) -> bool:
        if len(getters) <= 0:
            return False
        if len(getters) <= 1:
            return bool(await getters[0]())

        idx = 0
        res: bool
        while idx < len(getters):
            if idx == 0:
                res = await cls.async_short_calc(logic, getters[idx], getters[idx + 1])
                idx += 1
            else:

                async def res_getter() -> bool:
                    return res

                res = await cls.async_short_calc(logic, res_getter, getters[idx])
            idx += 1
        return res


def abstractattr(obj: Callable[[Any], T] | None = None) -> T:
    _obj = cast(Any, obj)
    if obj is None:
        _obj = BetterABCMeta.DummyAttribute()
    setattr(_obj, "__is_abstract_attribute__", True)
    return cast(T, _obj)


class BetterABCMeta(ABCMeta):

    class DummyAttribute: ...

    def __call__(cls: type[T], *args: Any, **kwargs: Any) -> T:
        instance = ABCMeta.__call__(cls, *args, **kwargs)
        lack_attrs = set()
        for name in dir(instance):
            try:
                attr = getattr(instance, name)
            except Exception:
                if not isinstance(getattr(instance.__class__, name), property):
                    raise

            if getattr(attr, "__is_abstract_attribute__", False):
                lack_attrs.add(name)
            if inspect.iscoroutine(attr):
                attr.close()

        if lack_attrs:
            raise NotImplementedError(
                "Can't instantiate abstract class {} with"
                " abstract attributes: {}".format(cls.__name__, ", ".join(lack_attrs))
            )
        return cast(T, instance)


class BetterABC(metaclass=BetterABCMeta):
    __slots__ = ()


class VoidType(Enum):
    VOID = type("_VOID", (), {})
