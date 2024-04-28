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


class DependManager:
    """依赖注入器"""

    @classmethod
    def inject(cls, func: AsyncCallable[P, T]) -> AsyncCallable[P, T]:

        @wraps(func)
        async def depend_wrapped(*args: Any, **kwargs: Any) -> T:
            signature = inspect.signature(func)
            all_params = {k: v for k, v in signature.parameters.items()}
            _args = list(args)
            defaults = {}

            for idx, _ in enumerate(_args):
                v = _args[idx]
                if isinstance(v, PendingDepend):
                    _args[idx] = await v.get()

            for idx, k in enumerate(kwargs.keys()):
                v = kwargs[k]
                if isinstance(v, PendingDepend):
                    kwargs[k] = await v.get()

            for idx, (k, v) in enumerate(all_params.items()):
                if idx < len(_args) or k in kwargs:
                    continue
                if isinstance(v.default, PendingDepend):
                    defaults[k] = await v.default.get()

            _kwargs = kwargs | defaults
            return await async_guard(func, *_args, **_kwargs)

        return depend_wrapped
