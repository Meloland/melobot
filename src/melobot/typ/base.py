from __future__ import annotations

from typing_extensions import TYPE_CHECKING, Any, Awaitable, ParamSpec, Protocol, TypeIs, TypeVar

from .._lazy import singleton

if TYPE_CHECKING:
    from beartype import BeartypeConf

__all__ = ("AsyncCallable", "P", "T", "T_co", "is_type", "is_subhint")

#: 泛型 T，无约束
T = TypeVar("T", default=Any)
#: 泛型 T，无约束
U = TypeVar("U", default=Any)
#: 泛型 T，无约束
V = TypeVar("V", default=Any)
#: 泛型 T_co，协变无约束
T_co = TypeVar("T_co", covariant=True, default=Any)
#: :obj:`~typing.ParamSpec` 泛型 P，无约束
P = ParamSpec("P", default=Any)
StrOrBytes = TypeVar("StrOrBytes", str, bytes)


class AsyncCallable(Protocol[P, T_co]):
    """用法：AsyncCallable[P, T]

    是该类型的等价形式：Callable[P, Awaitable[T]]
    """

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> Awaitable[T_co]: ...


class SyncOrAsyncCallable(Protocol[P, T_co]):
    """用法：SyncOrAsyncCallable[P, T]

    是该类型的等价形式：Callable[P, T | Awaitable[T]]
    """

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> T_co | Awaitable[T_co]: ...


@singleton
def _get_beartype_conf() -> "BeartypeConf":
    from beartype import BeartypeConf

    return BeartypeConf(is_pep484_tower=True)


def is_type(obj: T, hint: type[Any]) -> TypeIs[T]:
    """检查 `obj` 是否是类型注解 `hint` 所表示的类型

    :param obj: 任意对象
    :param hint: 任意类型注解
    :return: 布尔值
    """
    from beartype.door import is_bearable

    ret = is_bearable(obj, hint, conf=_get_beartype_conf())
    return ret  # type: ignore[no-any-return]


def is_subhint(subhint: Any, superhint: Any) -> bool:
    """检查 `subhint` 是否是 `superhint` 的子类型

    :param subhint: 任意类型注解
    :param superhint: 任意类型注解
    :return: 布尔值
    """
    from beartype.door import is_subhint as _is_subhint

    ret = _is_subhint(subhint, superhint)
    return ret  # type: ignore[no-any-return]
