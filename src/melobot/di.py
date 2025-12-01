from __future__ import annotations

from abc import abstractmethod
from asyncio import Lock
from dataclasses import dataclass
from functools import partial, wraps
from inspect import Parameter, isawaitable, signature
from types import BuiltinFunctionType, FunctionType, LambdaType, MethodType

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
    overload,
)

from .ctx import BotCtx, EventOrigin, FlowCtx, ParseArgsCtx, SessionCtx, get_logger_type
from .exceptions import DependInitError, DependRuntimeError
from .typ.base import AsyncCallable, P, SyncOrAsyncCallable, T, U, is_subhint, is_type
from .typ.cls import BetterABC
from .utils.base import to_async
from .utils.common import get_obj_name

if TYPE_CHECKING:
    from .adapter.base import Adapter


class DependNotMatched(BaseException):
    def __init__(
        self, msg: str, func_name: str, arg_name: str, real_type: type | None, hint: Any
    ) -> None:
        super().__init__(msg)
        self.func_name = func_name
        self.arg_name = arg_name
        self.real_type = real_type
        self.hint = hint


class Depends(Generic[T, U]):
    _EMPTY = object()

    @overload
    def __init__(
        self,
        dep: SyncOrAsyncCallable[[], T] | Depends[T],
        sub_getter: None = None,
        cache: bool = False,
        recursive: bool = True,
    ) -> None: ...

    @overload
    def __init__(
        self,
        dep: SyncOrAsyncCallable[[], U] | Depends[U],
        sub_getter: SyncOrAsyncCallable[[U], T],
        cache: bool = False,
        recursive: bool = True,
    ) -> None: ...

    def __init__(
        self,
        dep: SyncOrAsyncCallable[[], Any] | Depends[Any],
        sub_getter: SyncOrAsyncCallable[[Any], Any] | None = None,
        cache: bool = False,
        recursive: bool = True,
    ) -> None:
        """初始化一个依赖项

        :param dep: 依赖来源（可调用对象，异步可调用对象，或依赖项）
        :param sub_getter: 子获取器（可调用对象，异步可调用对象或空），在获得依赖之后，于其上继续获取
        :param cache: 是否启用缓存
        :param recursive: 是否启用递归满足（默认启用，如果 `dep` 和 `sub_getter` 为可调用对象，会自动被 {func}`.inject_deps` 装饰；关闭可节约性能）
        """
        super().__init__()
        self.ref: Depends[T] | None
        self.getter: AsyncCallable[[], T] | None

        if isinstance(dep, Depends):
            self.ref = dep
            self.getter = None
        else:
            self.ref = None
            if recursive:
                self.getter = inject_deps(dep)  # type: ignore[arg-type]
            else:
                self.getter = to_async(dep)  # type: ignore[arg-type]

        if sub_getter is None:
            self.sub_getter = None
        elif recursive:
            self.sub_getter = inject_deps(sub_getter)
        else:
            self.sub_getter = to_async(sub_getter)

        self._lock = Lock() if cache else None
        self._cached: Any = self._EMPTY

    def __repr__(self) -> str:
        getter_str = f"getter={self.getter}" if self.getter is not None else ""
        ref_str = f"ref={self.ref}" if self.ref is not None else ""
        return f"{self.__class__.__name__}({ref_str if ref_str != '' else getter_str})"

    async def _get(self, dep_scope: dict[Depends, Any]) -> T:
        if self.getter is not None:
            val = await self.getter()
        else:
            ref = cast(Depends[T], self.ref)
            val = dep_scope.get(ref, self._EMPTY)
            if val is self._EMPTY:
                val = await ref.fulfill(dep_scope)

        if self.sub_getter is not None:
            val = await self.sub_getter(val)
        return val

    async def fulfill(self, dep_scope: dict[Depends, Any]) -> T:
        if self._lock is None:
            val = await self._get(dep_scope)
        elif self._cached is not self._EMPTY:
            val = self._cached
        else:
            async with self._lock:
                if self._cached is self._EMPTY:
                    self._cached = await self._get(dep_scope)
                val = self._cached

        dep_scope[self] = val
        return val


class CbDepends(Depends, BetterABC, Generic[T]):
    """回调型依赖

    依赖项，但在依赖满足后，执行内部的回调
    """

    def __init__(
        self,
        dep: SyncOrAsyncCallable[[], Any],
        cache: bool = False,
        recursive: bool = False,
    ) -> None:
        super().__init__(dep, cache=cache, recursive=recursive)

    @abstractmethod
    async def deps_callback(self, val: Any) -> T:
        """所有子类必须实现该抽象方法

        :param val: 依赖项被满足后的值
        :return: 处理后的值，作为依赖项最终的值
        """
        return cast(T, val)

    async def fulfill(self, dep_scope: dict[Depends, Any]) -> T:
        val = await super().fulfill(dep_scope)
        new_val = await self.deps_callback(val)
        return new_val


class AutoDepends(CbDepends):
    def __init__(self, func: Callable, name: str, hint: Any) -> None:
        self.hint = hint
        self.func = func
        self.func_name = get_obj_name(func, otype="callable")
        self.arg_name = name

        self._match_event = False

        if get_origin(hint) is Annotated:
            args = get_args(hint)
            if not len(args):
                raise DependRuntimeError("可依赖注入的函数若使用 Annotated 注解，必须附加元数据")
            self.metadatas = args
        else:
            self.metadatas = ()

        self.orig_getter: SyncOrAsyncCallable[[], Any] | None = None

        if is_subhint(hint, FlowCtx().get_event_type()):
            self.orig_getter = FlowCtx().get_event

        elif is_subhint(hint, BotCtx().get_type()):
            self.orig_getter = BotCtx().get

        elif is_subhint(hint, _get_adapter_type()):
            self.orig_getter = cast(Callable[[], Any], partial(_adapter_get, self, hint))

        elif is_subhint(hint, get_logger_type()):
            self.orig_getter = BotCtx().get_logger

        elif is_subhint(hint, FlowCtx().get_store_type()):
            self.orig_getter = FlowCtx().get_store

        elif is_subhint(hint, SessionCtx().get_session_type()):
            self.orig_getter = SessionCtx().get

        elif is_subhint(hint, SessionCtx().get_store_type()):
            self.orig_getter = SessionCtx().get_store

        elif is_subhint(hint, SessionCtx().get_rule_type()):
            self.orig_getter = SessionCtx().get_rule

        elif is_subhint(hint, ParseArgsCtx().get_args_type()):
            self.orig_getter = ParseArgsCtx().get

        elif is_subhint(hint, FlowCtx().get_records_type()):
            self.orig_getter = FlowCtx().get_records

        for data in self.metadatas:
            if isinstance(data, MatchEvent):
                self._match_event = True

        if self.orig_getter is None:
            raise DependInitError(
                f"函数 {self.func_name} 的参数 {name} 提供的类型注解"
                f" {hint} 无法用于注入任何依赖，请检查是否有误"
            )

        for data in self.metadatas:
            if isinstance(data, Reflect):
                self.orig_getter = cast(Callable[[], Any], partial(Reflection, self.orig_getter))
                break

        super().__init__(self.orig_getter, cache=False, recursive=False)

    def _unmatch_exc(self, real_type: Any) -> DependNotMatched:
        if real_type is Depends._EMPTY:
            return DependNotMatched(
                f"函数 {self.func_name} 的参数 {self.arg_name} 对应的依赖项，"
                f"在当前上下文中不存在",
                self.func_name,
                self.arg_name,
                None,
                self.hint,
            )
        else:
            return DependNotMatched(
                f"函数 {self.func_name} 的参数 {self.arg_name} 与注解 {self.hint} 不匹配",
                self.func_name,
                self.arg_name,
                real_type,
                self.hint,
            )

    async def deps_callback(self, val: Any) -> Any:
        ret = val
        if isinstance(val, Reflection):
            val = val.__origin__

        for data in self.metadatas:
            if isinstance(data, Exclude):
                if any(isinstance(val, t) for t in data.types):
                    raise self._unmatch_exc(type(val))
        if not is_type(val, self.hint):
            raise self._unmatch_exc(type(val))
        return ret


def _get_adapter_type() -> type["Adapter"]:
    from .adapter.base import Adapter

    return Adapter


def _adapter_get(deps: AutoDepends, hint: Any) -> "Adapter":
    if not deps._match_event:
        if get_origin(hint) is Annotated:
            args = get_args(hint)
            if not len(args):
                raise DependRuntimeError("可依赖注入的函数若使用 Annotated 注解，必须附加元数据")
            adapter_type = args[0]
        else:
            adapter_type = hint

        adapter = BotCtx().get().get_adapter(adapter_type)
        if adapter is None:
            raise deps._unmatch_exc(Depends._EMPTY) from None
        return cast("Adapter", adapter)

    else:
        flow_ctx = FlowCtx()
        try:
            event = flow_ctx.get_event()
            return EventOrigin.get_origin(event).adapter
        except flow_ctx.lookup_exc_cls:
            raise deps._unmatch_exc(Depends._EMPTY) from None


@dataclass
class Exclude:
    """数据类。`types` 指定的类别会在依赖注入时被排除

    .. code:: python

        # 假设有 B 继承于 A, C 继承于 A, D 继承于 A
        # 表示不包括 B 和 C 类别的 A 的所有子类型：
        NewTypeHint = Annotated[A, Exclude(types=[B, C])]
        # 当然，依然会兼容 A 类型
    """

    types: Sequence[type]


@dataclass
class Reflect:
    """数据类。指定不直接获取当前依赖项，而是获取对应的一个反射代理

    这适用于希望依赖会随着上下文改变，而动态变化的情况。例如动态引用会话流程中的事件对象

    .. code:: python

        # 注入一个依赖时进一步包装为反射依赖
        ReflectedEvent = Annotated[Event, Reflect()]
        event_proxy: RefelectedEvent
        # 就像使用 event 一样使用 event_proxy
        event_proxy.attr_xxx
        event_proxy.method_xxx()

        # 不过 event_proxy 不是完美的代理
        # 因此 isinstance 类似的操作，使用 __origin__ 获取原始对象
        isinstance(event_proxy.__origin__, SomeEventType)
        # 或者是作为运行逻辑未知的函数的参数
        dont_know_what_this_do(event_proxy.__origin__)
    """


@dataclass
class MatchEvent:
    """数据类。指定从当前事件的上下文中获取依赖

    默认情况下，获取 Adapter 依赖都会直接尝试遍历所有可能的对象。

    即尽最大可能获取指定类型的对象。但有时需要实现这样的需求：

    .. code:: python

        # 假设 bot 已经加载了两个适配器：ObAdapter 和 XxAdapter
        from melobot.handle import on_event
        # 期待事件来自 ObAdapter 时，调用这个
        @on_event()
        async def on_onebot_event(adapter: ObAdapter) -> None: ...
        # 期待事件来自 XxAdapter 时，调用这个
        @on_event()
        async def on_xx_event(adapter: XxAdapter) -> None: ...

        # 但默认的逻辑是：bot 只要加载了对应的适配器，依赖就可以满足
        # 所以实际上他们都会被调用，没有任何区分效果

        # 使用 MatchEvent 来改变依赖获取的逻辑：
        # 事件的来源适配器必须和 MatchEvent 中指定的类型匹配，依赖才能满足
        @on_event()
        async def on_onebot_event(adapter: Annotated[ObAdapter, MatchEvent()]) -> None: ...
        @on_event()
        async def on_xx_event(adapter: Annotated[XxAdapter, MatchEvent()]) -> None: ...
    """


class Reflection:
    def __init__(self, getter: Callable[[], Any]) -> None:
        super().__setattr__("__obj_getter__", getter)

    @property
    def __origin__(self) -> Any:
        return self.__obj_getter__()

    def __getattr__(self, name: str) -> Any:
        getter = self.__obj_getter__
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


_DI_DEFAULTS = "MELOBOT_DI_TUPLE"
_DI_KW_DEFAULTS = "MELOBOT_DI_DICT"
_DI_INJECTED = "MELOBOT_DI_INJECTED"


def _init_auto_deps(func: Callable[P, T], allow_manual_arg: bool) -> None:
    # 无需再考虑对于多层装饰的兼容，signature 方法会获取原始签名
    # 若装饰过程在逻辑上改变了签名，这种情况属于错误用例，无需兼容
    sign = signature(func)
    empty = Parameter.empty
    args: list[Any] = []
    kwargs = {}

    for name, param in sign.parameters.items():
        # 可变位置参数或可变关键字参数时，无需任何操作
        if param.kind in (Parameter.VAR_POSITIONAL, Parameter.VAR_KEYWORD):
            continue

        # 有默认值的情况，保存默认值并跳过
        if param.default is not empty:
            if param.kind is Parameter.KEYWORD_ONLY:
                kwargs[name] = param.default
            else:
                args.append(param.default)
            continue

        # 没有默认值，没有注解的参数，跳过
        # 无法识别依赖类型，只能通过手动传参提供
        if param.annotation is empty:
            continue

        # 剩余情况需要注入自动依赖
        try:
            dep = None
            if get_origin(param.annotation) is Annotated:
                anno_args = get_args(param.annotation)
                if not len(anno_args):
                    raise DependRuntimeError(
                        "可依赖注入的函数若使用 Annotated 注解，必须附加元数据"
                    )
                for v in anno_args:
                    if isinstance(v, Depends):
                        dep = v
                        break
            if dep is None:
                dep = AutoDepends(func, name, param.annotation)
        except DependInitError:
            # 如果允许手动传参，无法识别的依赖显然是允许的
            if allow_manual_arg:
                continue
            raise

        if param.kind is Parameter.KEYWORD_ONLY:
            kwargs[name] = dep
        else:
            # 按照参数顺序遍历，添加到默认值列表是保序的
            args.append(dep)

    func.__dict__[_DI_DEFAULTS] = tuple(args)
    func.__dict__[_DI_KW_DEFAULTS] = kwargs
    func.__dict__[_DI_INJECTED] = True


def inject_deps(
    injectee: SyncOrAsyncCallable[..., T], manual_arg: bool = False, avoid_repeat: bool = False
) -> AsyncCallable[..., T]:
    """依赖注入标记装饰器，标记当前对象需要被依赖注入

    可以标记的对象类别有：
    同步函数，异步函数，匿名函数，同步生成器函数，异步生成器函数，实例方法、类方法、静态方法

    :param injectee: 需要被注入的对象
    :param manual_arg: 当前对象标记需要依赖注入后，是否还可以给某些参数手动传参
    :param avoid_repeat:
        是否避免在多层装饰时重复注入。检查内层装饰链，若内层装饰已有注入则放弃本次注入。
        但需要所有内层装饰使用 :func:`functools.wraps` 进行包装，否则无法检测
    :return: 异步可调用对象，但保留原始参数和返回值签名
    """

    @wraps(injectee)
    async def inject_deps_wrapped(*args: Any, **kwargs: Any) -> T:
        defaults: tuple[Any] = injectee.__dict__[_DI_DEFAULTS]
        kw_defaults: dict[str, Any] = injectee.__dict__[_DI_KW_DEFAULTS]
        # 模拟已有参数替换默认值的情况
        _args = [*args, *defaults[len(args) :]]
        _kwargs = kw_defaults.copy() | kwargs
        dep_scope: dict[Depends, Any] = {}

        for idx, _ in enumerate(_args):
            elem = _args[idx]
            if isinstance(elem, Depends):
                _args[idx] = await elem.fulfill(dep_scope)

        for k in _kwargs:
            elem = _kwargs[k]
            if isinstance(elem, Depends):
                _kwargs[k] = await elem.fulfill(dep_scope)

        try:
            ret = injectee(*_args, **_kwargs)  # type: ignore[arg-type]
        except TypeError as e:
            fname = get_obj_name(injectee, otype="callable")
            raise DependRuntimeError(
                f"依赖注入下的函数 {fname} 调用时发生错误：{e}。"
                "可能是参数存在问题：传参个数不匹配，或提供了错误的类型注解；"
                "或是函数内部逻辑错误。"
            ) from None

        if isawaitable(ret):
            return await ret
        return ret

    if avoid_repeat:
        f = injectee
        while True:
            if hasattr(f, _DI_INJECTED):
                return to_async(injectee)
            elif hasattr(f, "__wrapped__"):
                f = f.__wrapped__
            else:
                break

    if isinstance(injectee, (FunctionType, MethodType)):
        _init_auto_deps(injectee, manual_arg)
        return inject_deps_wrapped
    if isinstance(injectee, LambdaType):
        injectee.__dict__[_DI_DEFAULTS] = injectee.__defaults__ or ()
        injectee.__dict__[_DI_KW_DEFAULTS] = injectee.__kwdefaults__ or {}
        injectee.__dict__[_DI_INJECTED] = True
        return inject_deps_wrapped
    if isinstance(injectee, partial):
        injectee.__dict__[_DI_DEFAULTS] = injectee.args or ()
        injectee.__dict__[_DI_KW_DEFAULTS] = injectee.keywords or {}
        injectee.__dict__[_DI_INJECTED] = True
        return inject_deps_wrapped
    if isinstance(injectee, BuiltinFunctionType):
        raise DependInitError(f"内建函数 {injectee} 不支持依赖注入")

    raise DependInitError(
        f"{injectee} 对象不属于以下类别中的任何一种："
        "{同步函数，异步函数，匿名函数，partial 对象，同步生成器函数，异步生成器函数，"
        "实例方法、类方法、静态方法}，因此不能被注入依赖"
    )
