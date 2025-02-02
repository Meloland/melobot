import warnings
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
    TypeIs,
    TypeVar,
)

__all__ = (
    "AsyncCallable",
    "P",
    "T",
    "T_co",
    "is_type",
    "is_subhint",
    "deprecated",
    "deprecate_warn",
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


def is_type(obj: T, hint: type[Any]) -> TypeIs[T]:
    """检查 `obj` 是否是类型注解 `hint` 所表示的类型

    :param obj: 任意对象
    :param hint: 任意类型注解
    :return: 布尔值
    """
    ret = _is_type(obj, hint, conf=_DEFAULT_BEARTYPE_CONF)
    return ret  # type: ignore[no-any-return]


def deprecate_warn(msg: str) -> None:
    # pylint: disable=cyclic-import
    from ..ctx import LoggerCtx

    if logger := LoggerCtx().try_get():
        logger.warning(msg)
    warnings.simplefilter("always", DeprecationWarning)
    warnings.warn(msg, category=DeprecationWarning, stacklevel=1)
    warnings.simplefilter("default", DeprecationWarning)


def deprecated(msg: str) -> Callable[[Callable[P, T]], Callable[P, T]]:

    def deprecated_wrapper(func: Callable[P, T]) -> Callable[P, T]:

        @wraps(func)
        def deprecated_wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
            deprecate_warn(
                f"使用了弃用函数/方法 {func.__module__}.{func.__qualname__}: {msg}"
            )
            return func(*args, **kwargs)

        return deprecated_wrapped

    return deprecated_wrapper
