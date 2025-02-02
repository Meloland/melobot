import inspect
from abc import ABCMeta

from typing_extensions import Any, Callable, cast

from .base import T


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
