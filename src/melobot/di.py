from __future__ import annotations

from asyncio import Lock
from collections import deque
from dataclasses import dataclass
from functools import wraps
from inspect import Parameter, isawaitable, signature
from sys import version_info
from types import BuiltinFunctionType, FunctionType, LambdaType
from typing import Annotated, Any, Callable, Sequence, cast, get_args, get_origin

from .ctx import BotCtx, EventBuildInfoCtx, FlowCtx, LoggerCtx, SessionCtx
from .exceptions import DependBindError, DependInitError
from .typ import AsyncCallable, P, T, VoidType, is_subhint, is_type
from .utils import to_async


class DependNotMatched(BaseException):
    def __init__(
        self, msg: str, func_name: str, arg_name: str, real_type: type, hint: Any
    ) -> None:
        super().__init__(msg)
        self.func_name = func_name
        self.arg_name = arg_name
        self.real_type = real_type
        self.hint = hint


class Depends:
    def __init__(
        self,
        dep: Callable[[], Any] | AsyncCallable[[], Any] | Depends,
        sub_getter: Callable[[Any], Any] | AsyncCallable[[Any], Any] | None = None,
        cache: bool = False,
        recursive: bool = True,
    ) -> None:
        super().__init__()
        self.ref: Depends | None
        self.getter: AsyncCallable[[], Any] | None

        if isinstance(dep, Depends):
            self.ref = dep
            self.getter = None
        else:
            self.ref = None
            if recursive:
                self.getter = inject_deps(dep)
            else:
                self.getter = to_async(dep)

        if sub_getter is None:
            self.sub_getter = None
        elif recursive:
            self.sub_getter = inject_deps(sub_getter)
        else:
            self.sub_getter = to_async(sub_getter)

        self._lock = Lock() if cache else None
        self._cached: Any = VoidType.VOID

    def __repr__(self) -> str:
        getter_str = f"getter={self.getter}" if self.getter is not None else ""
        ref_str = f"ref={self.ref}" if self.ref is not None else ""
        return f"{self.__class__.__name__}({ref_str if ref_str != '' else getter_str})"

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


class AutoDepends(Depends):
    def __init__(self, func: Callable, name: str, hint: Any) -> None:
        self.hint = hint
        self.func = func
        self.arg_name = name

        if get_origin(hint) is Annotated:
            args = get_args(hint)
            if not len(args) == 2:
                raise DependInitError(
                    "可依赖注入的函数若使用 Annotated 注解，必须附加一个元数据信息，且最多只能有一个"
                )
            self.metadata = args[1]
        else:
            self.metadata = None

        self.orig_getter: Callable[[], Any] | AsyncCallable[[], Any]

        if is_subhint(hint, FlowCtx().get_event_type()):
            self.orig_getter = FlowCtx().get_event

        elif is_subhint(hint, BotCtx().get_type()):
            self.orig_getter = BotCtx().get

        elif is_subhint(hint, EventBuildInfoCtx().get_adapter_type()):
            self.orig_getter = lambda: EventBuildInfoCtx().get().adapter

        elif is_subhint(hint, LoggerCtx().get_type()):
            self.orig_getter = LoggerCtx().get

        elif is_subhint(hint, FlowCtx().get_store_type()):
            self.orig_getter = FlowCtx().get_store

        elif is_subhint(hint, SessionCtx().get_store_type()):
            self.orig_getter = SessionCtx().get_store

        elif isinstance(self.metadata, CustomLogger):
            self.orig_getter = LoggerCtx().get

        elif is_subhint(hint, SessionCtx().get_rule_type() | None):
            self.orig_getter = lambda: SessionCtx().get().rule

        else:
            raise DependInitError(
                f"函数 {func.__qualname__} 的参数 {name} 提供的类型注解 {hint} 无法用于注入任何依赖，请检查是否有误"
            )

        super().__init__(self.orig_getter, sub_getter=None, cache=False, recursive=False)

    def _get_unmatch_exc(self, real_type: Any) -> DependNotMatched:
        return DependNotMatched(
            f"函数 {self.func.__qualname__} 的参数 {self.arg_name} "
            f"与注解 {self.hint} 不匹配",
            self.func.__qualname__,
            self.arg_name,
            real_type,
            self.hint,
        )

    async def fulfill(self, dep_scope: dict[Depends, Any]) -> Any:
        val = await super().fulfill(dep_scope)

        if isinstance(self.metadata, Exclude):
            if any(isinstance(val, t) for t in self.metadata.types):
                raise self._get_unmatch_exc(type(val))

        elif isinstance(self.metadata, CustomLogger):
            if not is_type(val, self.hint):
                return self.metadata.getter()
            return val

        elif is_subhint(self.hint, LoggerCtx().get_type()):
            return val

        if is_type(val, self.hint):
            return val

        raise self._get_unmatch_exc(type(val))


@dataclass
class Exclude:
    types: Sequence[type]


@dataclass
class CustomLogger:
    getter: Callable[[], Any]


def _init_auto_deps(func: Callable[P, T], allow_manual_arg: bool) -> None:
    try:
        sign = signature(func)
    except ValueError as e:
        if (
            str(e).startswith("no signature found for builtin")
            and version_info.major >= 3
            and version_info.minor <= 10
        ):
            raise DependInitError(
                f"内建函数 {func} 在 python <= 3.10 的版本中，无法进行依赖注入"
            ) from None
        raise

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

        try:
            dep = AutoDepends(func, name, param.annotation)
        except DependInitError:
            if allow_manual_arg:
                continue
            raise

        if dep is None:
            continue

        if param.kind is Parameter.KEYWORD_ONLY:
            kwds[name] = dep
        else:
            vals.append(dep)

    func.__defaults__ = tuple(vals) if len(vals) else None
    func.__kwdefaults__ = kwds if len(kwds) else None  # type: ignore[assignment]


def _get_bound_args(
    func: Callable, /, *args: Any, **kwargs: Any
) -> tuple[list[Any], dict[str, Any]]:
    sign = signature(func)

    try:
        bind = sign.bind(*args, **kwargs)
    except TypeError as e:
        raise DependBindError(
            f"解析依赖时失败。匹配函数 {func.__qualname__} 的参数时发生错误：{e}。"
            "这可能是因为传参有误，或提供了错误的类型注解"
        ) from None

    bind.apply_defaults()
    return list(bind.args), bind.kwargs


def inject_deps(
    injectee: Callable[P, T] | AsyncCallable[P, T], manual_arg: bool = False
) -> AsyncCallable[P, T]:
    if hasattr(injectee, "__wrapped__"):
        raise DependInitError(
            f"函数 {injectee.__qualname__} 无法进行依赖注入，在依赖注入前它不能被装饰"
        )

    @wraps(injectee)
    async def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        _args, _kwargs = _get_bound_args(injectee, *args, **kwargs)
        dep_scope: dict[Depends, Any] = {}

        for idx, _ in enumerate(_args):
            elem = _args[idx]
            if isinstance(elem, Depends):
                _args[idx] = await elem.fulfill(dep_scope)

        for idx, k in enumerate(_kwargs.keys()):
            elem = _kwargs[k]
            if isinstance(elem, Depends):
                _kwargs[k] = await elem.fulfill(dep_scope)

        ret = injectee(*_args, **_kwargs)  # type: ignore[arg-type]
        if isawaitable(ret):
            return await ret
        return ret

    @wraps(injectee)
    async def class_wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        ret = cast(Callable[P, T], injectee)(*args, **kwargs)
        return ret

    if isinstance(injectee, (FunctionType, BuiltinFunctionType)):
        _init_auto_deps(injectee, manual_arg)
        return wrapped
    if isinstance(injectee, LambdaType):
        return wrapped
    if isinstance(injectee, type):
        return class_wrapped

    raise DependInitError(
        f"{injectee} 对象不属于以下类别中的任何一种："
        "{同步函数，异步函数，匿名函数，同步生成器函数，异步生成器函数，类对象，"
        "实例方法、类方法、静态方法}，因此不能被注入依赖"
    )
