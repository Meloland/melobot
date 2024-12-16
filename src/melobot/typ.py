import inspect
import warnings
from abc import ABCMeta, abstractmethod
from enum import Enum
from functools import wraps

from beartype import BeartypeConf as _BeartypeConf
from beartype.door import is_bearable as _is_type
from beartype.door import is_subhint
from typing_extensions import (
    Any,
    Awaitable,
    Callable,
    ParamSpec,
    Protocol,
    Self,
    Sequence,
    TypeGuard,
    TypeVar,
    cast,
)

__all__ = (
    "T",
    "T_co",
    "P",
    "AsyncCallable",
    "is_type",
    "is_subhint",
    "HandleLevel",
    "LogicMode",
    "BetterABCMeta",
    "BetterABCMeta",
    "BetterABC",
    "SingletonMeta",
    "SingletonBetterABCMeta",
    "abstractattr",
    "abstractmethod",
    "Markable",
    "AttrsReprable",
    "Locatable",
    "VoidType",
)

#: 泛型 T，无约束
T = TypeVar("T", default=Any)
#: 泛型 T_co，协变无约束
T_co = TypeVar("T_co", covariant=True, default=Any)
#: :obj:`~typing.ParamSpec` 泛型 P，无约束
P = ParamSpec("P", default=Any)


class AsyncCallable(Protocol[P, T_co]):
    """用法：AsyncCallable[P, T]

    是该类型的等价形式：Callable[P, Awaitable[T]]
    """

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> Awaitable[T_co]: ...


_DEFAULT_BEARTYPE_CONF = _BeartypeConf(is_pep484_tower=True)


def is_type(obj: T, hint: type[Any]) -> TypeGuard[T]:
    """检查 `obj` 是否是类型注解 `hint` 所表示的类型

    :param obj: 任意对象
    :param hint: 任意类型注解
    :return: 布尔值
    """
    ret = _is_type(obj, hint, conf=_DEFAULT_BEARTYPE_CONF)
    return ret


class HandleLevel(float, Enum):
    """事件处理流优先级枚举类型"""

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
        """将两个值使用指定逻辑模式运算

        :param logic: 逻辑模式
        :param v1: 值 1
        :param v2: 值 2
        :return: 布尔值
        """
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
        """与 :func:`calc` 功能类似，但运算支持短路

        :param logic: 逻辑模式
        :param v1: 生成值 1 的可调用对象
        :param v2: 生成值 2 的可调用对象
        :return: 布尔值
        """
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
        """与 :func:`short_calc` 功能类似，但运算支持异步

        :param logic: 逻辑模式
        :param v1: 生成值 1 的异步可调用对象
        :param v2: 生成值 2 的异步可调用对象
        :return: 布尔值
        """
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
        """使用指定的逻辑模式，对值序列进行运算

        .. code:: python

            # 操作等价与：True and False and True
            LogicMode.seq_calc(LogicMode.AND, [True, False, True])

        :param logic: 逻辑模式
        :param values: 值序列
        :return: 布尔值
        """
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
    def short_seq_calc(
        cls, logic: "LogicMode", getters: Sequence[Callable[[], Any]]
    ) -> bool:
        """与 :func:`seq_calc` 功能类似，但运算支持短路

        :param logic: 逻辑模式
        :param getters: 一组获取值的可调用对象
        :return: 布尔值
        """
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
        cls, logic: "LogicMode", getters: Sequence[AsyncCallable[[], Any]]
    ) -> bool:
        """与 :func:`short_seq_calc` 功能类似，但运算支持异步

        :param logic: 逻辑模式
        :param getters: 一组获取值的异步可调用对象
        :return: 布尔值
        """
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
    """抽象属性

    与 `abstractproperty` 相比更灵活，`abstractattr` 不关心你以何种形式定义属性。只要子类在实例化后，该属性存在，即认为合法。

    但注意它必须与 :class:`BetterABC` 或 :class:`BetterABCMeta` 或 :class:`.SingletonBetterABCMeta` 配合使用

    这意味着可以在类层级、实例层级定义属性，或使用 `property` 定义属性：

    .. code:: python

        class A(BetterABC):
            foo: int = abstractattr()  # 声明为抽象属性

            # 或者使用装饰器的形式声明，这与上面是等价的
            @abstractattr
            def bar(self) -> int: ...

        # 以下实现都是合法的：

        class B(A):
            foo = 2
            bar = 4

        class C(A):
            foo = 3
            def __init__(self) -> None:
                self.bar = 5

        class D(A):
            def __init__(self) -> None:
                self.foo = 8

            @property
            def bar(self) -> int:
                return self.foo + 10
    """
    _obj = cast(Any, obj)
    if obj is None:
        _obj = BetterABCMeta.DummyAttribute()
    setattr(_obj, "__is_abstract_attribute__", True)
    return cast(T, _obj)


class BetterABCMeta(ABCMeta):
    """更好的抽象元类，兼容 `ABCMeta` 的所有功能，但是额外支持 :func:`abstractattr`"""

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
    """更好的抽象类，兼容 `ABC` 的所有功能，但是额外支持 :func:`abstractattr`"""

    __slots__ = ()


class SingletonMeta(type):
    """单例元类

    相比单例装饰器，可以自动保证所有子类都为单例
    """

    __instances__: dict[type, Any] = {}

    def __call__(cls: type[T], *args: Any, **kwargs: Any) -> T:
        if cls not in SingletonMeta.__instances__:
            SingletonMeta.__instances__[cls] = cast(
                T, super(SingletonMeta, cls).__call__(*args, **kwargs)  # type: ignore[misc]
            )
        return cast(T, SingletonMeta.__instances__[cls])


class SingletonBetterABCMeta(BetterABCMeta):
    """单例抽象元类

    相比普通的抽象元类，还可以自动保证所有子类都为单例
    """

    __instances__: dict[type, Any] = {}

    def __call__(cls: type[T], *args: Any, **kwargs: Any) -> T:
        mcls = SingletonBetterABCMeta
        if cls not in mcls.__instances__:
            mcls.__instances__[cls] = BetterABCMeta.__call__(cls, *args, **kwargs)
        return cast(T, mcls.__instances__[cls])


class Markable:
    """可标记对象

    无需直接实例化，而是用作接口在其他类中继承
    """

    def __init__(self) -> None:
        self._flags: dict[str, dict[str, Any]] = {}

    def flag_mark(self, namespace: str, flag_name: str, val: Any = None) -> None:
        """在 `namespace` 命名空间中设置 `flag_name` 标记，值为 `val`

        注：不同的对象并不共享 `namespace`，`namespace` 只适用于单个对象

        :param namespace: 命名空间
        :param flag_name: 标记名
        :param val: 标记值
        """
        self._flags.setdefault(namespace, {})

        if flag_name in self._flags[namespace].keys():
            raise ValueError(
                f"标记失败。对象的命名空间 {namespace} 中已存在名为 {flag_name} 的标记"
            )

        self._flags[namespace][flag_name] = val

    def flag_check(self, namespace: str, flag_name: str, val: Any = None) -> bool:
        """检查 `namespace` 命名空间中 `flag_name` 标记值是否为 `val`

        注：不同的对象并不共享 `namespace`，`namespace` 只适用于单个对象

        :param namespace: 命名空间
        :param flag_name: 标记名
        :param val: 标记值
        :return: 是否通过检查
        """
        if self._flags.get(namespace) is None:
            return False
        if flag_name not in self._flags[namespace].keys():
            return False
        flag = self._flags[namespace][flag_name]

        if val is None:
            return flag is None
        return cast(bool, flag == val)


class AttrsReprable:
    def __repr__(self) -> str:
        attrs = ", ".join(
            f"{k}={repr(v)}" for k, v in self.__dict__.items() if not k.startswith("_")
        )
        return f"{self.__class__.__name__}({attrs})"


class Locatable:
    def __new__(cls, *_args: Any, **_kwargs: Any) -> Self:
        obj = super().__new__(cls)
        obj.__obj_location__ = obj._init_location()  # type: ignore[attr-defined]
        return obj

    def __init__(self) -> None:
        self.__obj_location__: tuple[str, str, int]

    @staticmethod
    def _init_location() -> tuple[str, str, int]:
        frame = inspect.currentframe()
        while frame:
            if frame.f_code.co_name == "<module>":
                return (
                    frame.f_globals["__name__"],
                    frame.f_globals["__file__"],
                    frame.f_lineno,
                )
            frame = frame.f_back

        return (
            "<unknown module>",
            "<unknown file>",
            -1,
        )

    @property
    def __obj_module__(self) -> str:
        return self.__obj_location__[0]

    @property
    def __obj_file__(self) -> str:
        return self.__obj_location__[1]

    @property
    def __obj_line__(self) -> int:
        return self.__obj_location__[2]


class VoidType(Enum):
    """空类型，需要区别于 `None` 时使用

    .. code:: python

        # 有些时候 `None` 也是合法值，因此需要一个额外的哨兵值：
        def foo(val: Any | VoidType = VoidType.VOID) -> None:
            ...
    """

    VOID = type("_VOID", (), {})


def deprecate_warn(msg: str) -> None:
    # pylint: disable=cyclic-import
    from .ctx import LoggerCtx

    if logger := LoggerCtx().try_get():
        logger.warning(msg)
    warnings.simplefilter("always", DeprecationWarning)
    warnings.warn(msg, category=DeprecationWarning, stacklevel=1)
    warnings.simplefilter("default", DeprecationWarning)


def deprecated(msg: str) -> Callable[[Callable[P, T]], Callable[P, T]]:

    def decorator(func: Callable[P, T]) -> Callable[P, T]:

        @wraps(func)
        def deprecate_wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
            deprecate_warn(
                f"使用了弃用函数/方法 {func.__module__}.{func.__qualname__}: {msg}"
            )
            return func(*args, **kwargs)

        return deprecate_wrapped

    return decorator
