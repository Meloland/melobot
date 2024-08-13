from asyncio import Lock
from collections import deque
from functools import wraps
from inspect import Parameter, Signature, isawaitable, signature

from .exceptions import BotDependError
from .log import Logger, _Logger, get_logger
from .typ import (
    Any,
    AsyncCallable,
    Callable,
    FunctionType,
    Generic,
    LambdaType,
    Literal,
    P,
    T,
    VoidType,
    cast,
    is_type,
)


class Depends(Generic[T]):
    def __init__(
        self, callback: AsyncCallable[[], T] | Callable[[], T], cache: bool = False
    ) -> None:
        super().__init__()
        self.getter = inject_deps(callback)
        self._lock = Lock() if cache else None
        self._cached: T | Literal[VoidType.VOID] = VoidType.VOID

    async def fulfill(self) -> T:
        if self._lock is None:
            return await self.getter()

        if self._cached is not VoidType.VOID:
            return self._cached
        async with self._lock:
            if self._cached is VoidType.VOID:
                self._cached = await self.getter()
            return self._cached


def _find_explict_dep(typ: Any) -> Depends[Any] | None:
    if is_type(typ, type[Logger | _Logger]):
        return Depends(get_logger)
    else:
        return None


def _init_explict_deps(func: Callable[P, T]) -> None:
    sign = signature(func)
    ds = deque(func.__defaults__) if func.__defaults__ is not None else deque()
    kwds = func.__kwdefaults__ if func.__kwdefaults__ is not None else {}
    vals: list[Any] = []
    _empty = Parameter.empty

    for name, param in sign.parameters.items():
        if param.kind in (Parameter.VAR_POSITIONAL, Parameter.VAR_KEYWORD):
            continue

        if param.default is not _empty:
            if name in kwds:
                pass
            else:
                ds.popleft()
                vals.append(param.default)
            continue

        if param.annotation is _empty:
            continue

        dep = _find_explict_dep(param.annotation)
        if dep is None:
            continue

        if param.kind is Parameter.KEYWORD_ONLY:
            kwds[name] = dep
        else:
            vals.append(dep)

    func.__defaults__ = tuple(vals) if len(vals) else None
    func.__kwdefaults__ = kwds if len(kwds) else None  # type: ignore[assignment]


def _get_bound_args(
    func: Callable, /, *args, **kwargs
) -> tuple[list[Any], dict[str, Any]]:
    sign = signature(func)
    try:
        bind = sign.bind(*args, **kwargs)
    except TypeError as e:
        raise BotDependError(f"{func.__qualname__} 传参错误：{e}")
    bind.apply_defaults()
    return list(bind.args), bind.kwargs


def inject_deps(callee: Callable[P, T] | AsyncCallable[P, T]) -> AsyncCallable[P, T]:
    if isinstance(callee, FunctionType):
        _init_explict_deps(callee)
    elif isinstance(callee, LambdaType):
        pass
    else:
        raise BotDependError(f"只有可调用对象能被注入依赖，但 {callee} 不是可调用对象")

    @wraps(callee)
    async def async_wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        _args, _kwargs = _get_bound_args(callee, *args, **kwargs)

        for idx, _ in enumerate(_args):
            elem = _args[idx]
            if isinstance(elem, Depends):
                _args[idx] = await elem.fulfill()

        for idx, k in enumerate(_kwargs.keys()):
            elem = _kwargs[k]
            if isinstance(elem, Depends):
                _kwargs[k] = await elem.fulfill()

        ret = callee(*_args, **_kwargs)  # type: ignore[arg-type]
        if isawaitable(ret):
            return await ret
        else:
            return cast(T, ret)

    return async_wrapped
