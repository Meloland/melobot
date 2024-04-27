import inspect
from functools import wraps
from inspect import isawaitable

from .typing import Any, AsyncCallable, Callable, Generic, P, T, async_guard, cast


class PendingDepend(Generic[T]):
    """悬垂依赖，意味着依赖将稍后满足"""

    def __init__(self, getter: AsyncCallable[[], T] | Callable[[], T]) -> None:
        super().__init__()
        self.getter = getter

    async def get(self) -> T:
        res = self.getter()
        if isawaitable(res):
            return await res
        else:
            return cast(T, res)


def get_default_args(func) -> dict[str, Any]:
    signature = inspect.signature(func)
    return {
        k: v.default
        for k, v in signature.parameters.items()
        if v.default is not inspect.Parameter.empty
    }


class DependManager:
    """依赖注入器"""

    @classmethod
    def inject(cls, func: AsyncCallable[P, T]) -> AsyncCallable[P, T]:

        @wraps(func)
        async def depend_wrapped(*args: Any, **kwargs: Any) -> T:
            defaults = get_default_args(func)
            for k, v in defaults.items():
                if isinstance(v, PendingDepend) and kwargs.get(k) is None:
                    defaults[k] = await v.get()

            _kwargs = defaults | kwargs
            return await async_guard(func, *args, **_kwargs)

        return depend_wrapped
