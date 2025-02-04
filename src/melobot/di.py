from __future__ import annotations

from asyncio import Lock
from collections import deque
from dataclasses import dataclass
from functools import wraps
from inspect import Parameter, isawaitable, signature, unwrap
from sys import version_info
from types import BuiltinFunctionType, FunctionType, LambdaType

from typing_extensions import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Callable,
    Generic,
    Sequence,
    cast,
    get_args,
    get_origin,
)

from .ctx import BotCtx, EventBuildInfoCtx, FlowCtx, LoggerCtx, SessionCtx
from .exceptions import DependBindError, DependInitError
from .typ import (
    AsyncCallable,
    BetterABC,
    P,
    T,
    VoidType,
    abstractmethod,
    is_subhint,
    is_type,
)
from .utils import get_obj_name, to_async

if TYPE_CHECKING:
    from .adapter.base import Adapter


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
        """初始化一个依赖项

        :param dep: 依赖来源（可调用对象，异步可调用对象，或依赖项）
        :param sub_getter: 子获取器（可调用对象，异步可调用对象或空），在获得依赖之后，于其上继续获取
        :param cache: 是否启用缓存
        :param recursive: 是否启用递归满足（默认启用，如果当前依赖来源中存在依赖项，会被递归满足；关闭可节约性能）
        """
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


def _adapter_get(hint: Any) -> "Adapter":
    ctx = EventBuildInfoCtx()
    try:
        return ctx.get().adapter
    except ctx.lookup_exc_cls as e:
        adapter = BotCtx().get().get_adapter(hint)
        if adapter is None:
            raise e
        return adapter


def _custom_logger_get(hint: Any, data: CustomLogger) -> Any:
    val = LoggerCtx().get()
    if not is_type(val, hint):
        val = data.getter()
    return val


class AutoDepends(Depends):
    def __init__(self, func: Callable, name: str, hint: Any) -> None:
        self.hint = hint
        self.func = func
        self.func_name = get_obj_name(func, otype="callable")
        self.arg_name = name

        if get_origin(hint) is Annotated:
            args = get_args(hint)
            if not len(args):
                raise DependInitError(
                    "可依赖注入的函数若使用 Annotated 注解，必须附加元数据"
                )
            self.metadatas = args
        else:
            self.metadatas = ()

        self.orig_getter: Callable[[], Any] | AsyncCallable[[], Any] | None = None

        if is_subhint(hint, FlowCtx().get_event_type()):
            self.orig_getter = FlowCtx().get_event

        elif is_subhint(hint, BotCtx().get_type()):
            self.orig_getter = BotCtx().get

        elif is_subhint(hint, EventBuildInfoCtx().get_adapter_type()):
            self.orig_getter = cast(Callable[[], Any], lambda h=hint: _adapter_get(h))

        elif is_subhint(hint, LoggerCtx().get_type()):
            self.orig_getter = LoggerCtx().get

        elif is_subhint(hint, FlowCtx().get_store_type()):
            self.orig_getter = FlowCtx().get_store

        elif is_subhint(hint, SessionCtx().get_store_type()):
            self.orig_getter = SessionCtx().get_store

        elif is_subhint(hint, SessionCtx().get_rule_type() | None):
            self.orig_getter = lambda: SessionCtx().get().rule

        for data in self.metadatas:
            if isinstance(data, CustomLogger):
                self.orig_getter = cast(
                    Callable[[], Any], lambda h=hint, d=data: _custom_logger_get(h, d)
                )
                break

        if self.orig_getter is None:
            raise DependInitError(
                f"函数 {self.func_name} 的参数 {name} 提供的类型注解"
                f" {hint} 无法用于注入任何依赖，请检查是否有误"
            )

        for data in self.metadatas:
            if isinstance(data, Reflect):
                self.orig_getter = cast(
                    Callable[[], Any],
                    lambda g=self.orig_getter: Reflection(cast(Callable[[], Any], g)),
                )
                break

        super().__init__(self.orig_getter, sub_getter=None, cache=False, recursive=False)

    def _unmatch_exc(self, real_type: Any) -> DependNotMatched:
        return DependNotMatched(
            f"函数 {self.func_name} 的参数 {self.arg_name} " f"与注解 {self.hint} 不匹配",
            self.func_name,
            self.arg_name,
            real_type,
            self.hint,
        )

    def _match_check(self, val: Any) -> None:
        for data in self.metadatas:
            if isinstance(data, Exclude):
                if any(isinstance(val, t) for t in data.types):
                    raise self._unmatch_exc(type(val))

        for data in self.metadatas:
            if isinstance(data, CustomLogger):
                return

        if not is_type(val, self.hint):
            raise self._unmatch_exc(type(val))

    async def fulfill(self, dep_scope: dict[Depends, Any]) -> Any:
        val = await super().fulfill(dep_scope)

        if isinstance(val, Reflection):
            inner_val = val.__obj_getter__()
            if isawaitable(inner_val):
                raise AttributeError(
                    f"异步依赖项不能通过 {Reflect.__name__} 创建反射依赖"
                )

            self._match_check(inner_val)
            return val

        self._match_check(val)
        return val


@dataclass
class Exclude:
    """数据类。`types` 指定的类别会在依赖注入时被排除

    .. code:: python

        # 假设有继承关系 A <- B, A <- C, A <- D
        # 表示 A 中不包括 B 和 C 类别的所有子类型，当然，还是会兼容 A 类型本身
        NewTypeHint = Annotated[A, Exclude(types=[B, C])]
    """

    types: Sequence[type]


@dataclass
class CustomLogger:
    """数据类。`getter` 参数会用于指定类别日志器不存在时的获取方法

    .. code:: python

        # 如果 bot 设置的 logger 是 MyLogger 类型，则成功依赖注入
        # 否则使用 getter 获取一个日志器
        NewLoggerHint = Annotated[MyLogger, CustomLogger(getter=lambda: MyLogger())]
    """

    getter: Callable[[], Any]


@dataclass
class Reflect:
    """数据类。指定不直接获取当前依赖项，而是获取对应的一个反射代理

    这适用于希望依赖会随着上下文改变，而动态变化的情况。例如动态引用会话流程中的事件对象

    .. code:: python

        # 注入一个依赖时进一步包装为反射依赖
        event_proxy = Annotated[Event, Reflect()]
        # 就像使用 event 一样使用 event_proxy
        event_proxy.attr_xxx
        event_proxy.method_xxx()

        # 不过 event_proxy 不是完美的代理
        # 因此 isinstance 类似的操作，使用 __origin__ 获取原始对象
        isinstance(event_proxy.__origin__, SomeEventType)
        # 或者是作为运行逻辑未知的函数的参数
        dont_know_what_this_do(event_proxy.__origin__)
    """


class Reflection:
    def __init__(self, getter: Callable[[], Any]) -> None:
        super().__setattr__("__obj_getter__", getter)

    @property
    def __origin__(self) -> Any:
        return self.__obj_getter__()

    def __getattr__(self, name: str) -> Any:
        getter = self.__obj_getter__
        if name == "__obj_getter__":
            return getter
        if name.startswith("_"):
            raise AttributeError(f"在反射对象上，不允许访问名称以 _ 开头的属性：{name}")

        return getattr(getter(), name)

    def __setattr__(self, name: str, value: Any) -> Any:
        getter = self.__obj_getter__
        if name == "__obj_getter__":
            return getter
        if name.startswith("_"):
            raise AttributeError(f"在反射对象上，不允许修改名称以 _ 开头的属性：{name}")

        return setattr(getter(), name, value)


def _init_auto_deps(func: Callable[P, T], allow_manual_arg: bool) -> None:
    try:
        sign = signature(func)
    except ValueError as e:
        tip = "no signature found for builtin"
        if str(e).startswith(tip) and version_info <= (3, 10):
            raise DependInitError(
                f"内建函数 {func} 在 python <= 3.10 的版本中，无法进行依赖注入"
            ) from None
        raise

    empty = Parameter.empty
    origin_f = unwrap(func, stop=lambda f: hasattr(f, "__signature__"))
    ds = deque(origin_f.__defaults__) if origin_f.__defaults__ is not None else deque()
    kwds = origin_f.__kwdefaults__ if origin_f.__kwdefaults__ is not None else {}
    nargs: list[Any] = []

    for name, param in sign.parameters.items():
        if param.kind in (Parameter.VAR_POSITIONAL, Parameter.VAR_KEYWORD):
            continue

        if param.default is not empty:
            if name in kwds:
                pass
            else:
                ds.popleft()
                nargs.append(param.default)
            continue

        if param.annotation is empty:
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
            nargs.append(dep)

    origin_f.__defaults__ = tuple(nargs) if len(nargs) else None
    origin_f.__kwdefaults__ = kwds if len(kwds) else None  # type: ignore[assignment]


def _get_bound_args(
    func: Callable, /, *args: Any, **kwargs: Any
) -> tuple[list[Any], dict[str, Any]]:
    sign = signature(func)

    try:
        bind = sign.bind(*args, **kwargs)
    except TypeError as e:
        fname = get_obj_name(func, otype="callable")
        raise DependBindError(
            f"依赖注入匹配失败。匹配函数 {fname} 的参数时发生错误：{e}。"
            "这可能是因为传参个数不匹配，或提供了错误的类型注解"
        ) from None

    bind.apply_defaults()
    return list(bind.args), bind.kwargs


class DependsHook(Depends, BetterABC, Generic[T]):
    """依赖钩子

    包装一个依赖项，依赖满足后内部的 hook 将会执行
    """

    def __init__(
        self,
        func: Callable[P, T] | AsyncCallable[P, T],
        cache: bool = False,
        recursive: bool = False,
    ) -> None:
        super().__init__(func, cache=cache, recursive=recursive)

    @abstractmethod
    async def deps_callback(self, val: T) -> None:
        """所有依赖钩子子类必须实现该抽象方法

        :param val: 依赖项被满足后的值
        """
        raise NotImplementedError

    async def fulfill(self, dep_scope: dict[Depends, Any]) -> Any:
        val = await super().fulfill(dep_scope)
        await self.deps_callback(val)
        return val


def inject_deps(
    injectee: Callable[..., T] | AsyncCallable[..., T], manual_arg: bool = False
) -> AsyncCallable[..., T]:
    """依赖注入标记装饰器，标记当前对象需要被依赖注入

    可以标记的对象类别有：
    同步函数，异步函数，匿名函数，同步生成器函数，异步生成器函数，实例方法、类方法、静态方法

    :param injectee: 需要被注入的对象
    :param manual_arg: 当前对象标记需要依赖注入后，是否还可以给某些参数手动传参
    :return: 异步可调用对象，但保留原始参数和返回值签名
    """

    @wraps(injectee)
    async def di_wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
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

    if isinstance(injectee, (FunctionType, BuiltinFunctionType)):
        _init_auto_deps(injectee, manual_arg)
        return di_wrapped
    if isinstance(injectee, LambdaType):
        return di_wrapped

    raise DependInitError(
        f"{injectee} 对象不属于以下类别中的任何一种："
        "{同步函数，异步函数，匿名函数，同步生成器函数，异步生成器函数，"
        "实例方法、类方法、静态方法}，因此不能被注入依赖"
    )
