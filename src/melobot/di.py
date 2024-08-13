from __future__ import annotations

from asyncio import Lock
from collections import deque
from functools import wraps
from inspect import Parameter, isawaitable, signature

from .exceptions import BotDependError
from .log import Logger, _Logger, get_logger
from .typ import (
    Any,
    AsyncCallable,
    Callable,
    FunctionType,
    Generic,
    LambdaType,
    P,
    T,
    TypeVar,
    VoidType,
    cast,
    is_type,
)

Main_T = TypeVar("Main_T")
Sub_T = TypeVar("Sub_T")


class Depends(Generic[Main_T, Sub_T]):
    def __init__(
        self,
        dep: Callable[[], Main_T] | AsyncCallable[[], Main_T] | Depends[Any, Main_T],
        sub_getter: (
            Callable[[Main_T], Sub_T] | AsyncCallable[[Main_T], Sub_T] | None
        ) = None,
        cache: bool = False,
    ) -> None:
        super().__init__()
        self.ref: Depends | None
        self.getter: AsyncCallable[[], Any] | None
        if isinstance(dep, Depends):
            self.ref = dep
            self.getter = None
        else:
            self.ref = None
            self.getter = inject_deps(dep)
        self.sub_getter = None if sub_getter is None else inject_deps(sub_getter)

        self._lock = Lock() if cache else None
        self._cached: Any = VoidType.VOID

    def __repr__(self) -> str:
        getter_str = f"getter={self.getter}" if self.getter is not None else ""
        ref_str = f"ref={self.ref}" if self.ref is not None else ""
        return f"Depends({ref_str if ref_str != '' else getter_str})"

    async def _get(self, dep_scope: dict[Depends, Any]) -> Any:
        if self.getter is not None:
            val = await self.getter()
        else:
            ref = cast(Depends, self.ref)
            val = dep_scope.get(ref, VoidType.VOID)
            if val is VoidType.VOID:
                val = await ref.fulfill(dep_scope)

        if self.sub_getter is not None:
            val = self.sub_getter(val)
            if isawaitable(val):
                val = await val
        return val

    async def fulfill(self, dep_scope: dict[Depends, Any]) -> Any:
        if self._lock is None:
            val = await self._get(dep_scope)
        elif self._cached is not VoidType.VOID:
            val = self._cached
        else:
            async with self._lock:
                if self._cached is VoidType.VOID:
                    self._cached = await self._get(dep_scope)
                val = self._cached

        dep_scope[self] = val
        return val


def _find_explict_dep(typ: Any) -> Depends | None:
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
    @wraps(callee)
    async def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        _args, _kwargs = _get_bound_args(callee, *args, **kwargs)
        dep_scope: dict[Depends, Any] = {}

        for idx, _ in enumerate(_args):
            elem = _args[idx]
            if isinstance(elem, Depends):
                _args[idx] = await elem.fulfill(dep_scope)

        for idx, k in enumerate(_kwargs.keys()):
            elem = _kwargs[k]
            if isinstance(elem, Depends):
                _kwargs[k] = await elem.fulfill(dep_scope)

        ret = callee(*_args, **_kwargs)  # type: ignore[arg-type]
        if isawaitable(ret):
            return await ret
        else:
            return cast(T, ret)

    @wraps(callee)
    async def class_wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        ret = cast(Callable, callee)(*args, **kwargs)
        return ret

    if isinstance(callee, FunctionType):
        _init_explict_deps(callee)
        return wrapped
    elif isinstance(callee, LambdaType):
        return wrapped
    elif isinstance(callee, type):
        return class_wrapped
    else:
        raise BotDependError(
            f"{callee} 对象不属于以下类别中的任何一种：{{同步函数，异步函数，匿名函数，同步生成器函数，异步生成器函数，类对象，实例方法、类方法、静态方法}}，因此不能被注入依赖"
        )
