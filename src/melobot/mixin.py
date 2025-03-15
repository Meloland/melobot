import inspect
from asyncio import Future, get_running_loop

from typing_extensions import Any, Callable, Generic, Self, cast

from ._hook import HookBus, HookEnumT
from .ctx import LoggerCtx
from .log.base import GenericLogger
from .typ.base import AsyncCallable, P, SyncOrAsyncCallable
from .utils.base import to_async


class LogMixin:
    """日志混合类"""

    @property
    def logger(self) -> GenericLogger:
        return LoggerCtx().get()


class FlagMixin:
    """标记混合类"""

    def __init__(self) -> None:
        self.__flag_mixin_flags__: dict[Any, dict[Any, Any]] = {}
        self.__flag_mixin_waitings__: dict[
            tuple[Any, Any], list[tuple[Any, Future, bool, bool]]
        ] = {}

    def __flag_waitings_fulfill__(self, namespace: Any, flag: Any, val: Any) -> None:
        waitings = self.__flag_mixin_waitings__.get((namespace, flag))
        if waitings is None:
            return

        for waiting in waitings:
            expect_val, signal, use_id, wait_val = waiting
            if not wait_val:
                signal.set_result(None)
                continue

            if use_id and val is expect_val:
                signal.set_result(None)
                continue

            if not use_id and val == expect_val:
                signal.set_result(None)
                continue

    def flag_set(
        self,
        namespace: Any,
        flag: Any,
        val: Any = None,
        strict: bool = True,
    ) -> None:
        """设置标记

        注：不同的对象并不共享 `namespace`，`namespace` 只适用于单个对象

        :param namespace: 命名空间
        :param flag: 标记
        :param val: 标记值
        :param strict: 严格模式，启用严格模式，则不允许 `flag` 标记已经存在
        """
        self.__flag_mixin_flags__.setdefault(namespace, {})

        if strict and flag in self.__flag_mixin_flags__[namespace].keys():
            raise ValueError(
                f"标记失败。对象 {self} 的命名空间 {namespace} 中已存在名为 {flag} 的标记"
            )

        self.__flag_mixin_flags__[namespace][flag] = val
        self.__flag_waitings_fulfill__(namespace, flag, val)

    def flag_set_default(self, namespace: Any, flag: Any, default: Any) -> None:
        """设置标记，并在标记不存在时使用 `default` 初始化

        注：不同的对象并不共享 `namespace`，`namespace` 只适用于单个对象

        :param namespace: 命名空间
        :param flag: 标记
        :param default: 标记不存在时的默认值
        """
        self.__flag_mixin_flags__.setdefault(namespace, {})
        self.__flag_mixin_flags__[namespace].setdefault(flag, default)
        val = self.__flag_mixin_flags__[namespace][flag]
        self.__flag_waitings_fulfill__(namespace, flag, val)

    def flag_get(
        self, namespace: Any, flag: Any, raise_exc: bool = True, default: Any = None
    ) -> Any:
        """获取标记值

        注：不同的对象并不共享 `namespace`，`namespace` 只适用于单个对象

        :param namespace: 命名空间
        :param flag: 标记
        :param raise_exc: 为 `True`，则在标记不存在时引发 `KeyError`
        :param default: 标记不存在时的默认值，只在 `raise_exc` 为 `False` 时有效
        :return: 标记值
        """
        try:
            return self.__flag_mixin_flags__[namespace][flag]
        except KeyError:
            if raise_exc:
                raise KeyError(
                    f"对象 {self} 的命名空间 {namespace} 中不存在名为 {flag} 的标记"
                ) from None
            return default

    def flag_check(
        self,
        namespace: Any,
        flag: Any,
        val: Any = None,
        check_val: bool = True,
        use_id: bool = False,
    ) -> bool:
        """检查标记

        注：不同的对象并不共享 `namespace`，`namespace` 只适用于单个对象

        :param namespace: 命名空间
        :param flag: 标记
        :param val: 标记值
        :param check_val: 为 `True` 则需要值也一致
        :param use_id: 为 `True` 则使用 `is` 判断 `val`，否则调用 `==` 判断 `val`
        :return: 是否通过检查
        """
        if namespace not in self.__flag_mixin_flags__.keys():
            return False
        if flag not in self.__flag_mixin_flags__[namespace].keys():
            return False
        flag = self.__flag_mixin_flags__[namespace][flag]

        if not check_val:
            return True
        if use_id:
            return flag is val
        return cast(bool, flag == val)

    async def flag_wait(
        self,
        namespace: Any,
        flag: Any,
        val: Any = None,
        wait_val: bool = True,
        use_id: bool = False,
    ) -> None:
        """等待标记

        注：不同的对象并不共享 `namespace`，`namespace` 只适用于单个对象

        :param namespace: 命名空间
        :param flag: 标记
        :param val: 标记值
        :param wait_val: 为 `True` 则需要值也一致
        :param use_id: 为 `True` 则使用 `is` 判断 `val`，否则调用 `==` 判断 `val`
        """
        if self.flag_check(namespace, flag, val, wait_val, use_id):
            return None

        signal: Future[None] = get_running_loop().create_future()
        waitings = self.__flag_mixin_waitings__.setdefault((namespace, flag), [])
        waitings.append((val, signal, use_id, wait_val))
        await signal
        waitings = list(filter(lambda x: not x[1].done(), waitings))
        if not len(waitings):
            self.__flag_mixin_waitings__.pop((namespace, flag))


class AttrReprMixin:
    """属性 repr 混合类

    继承后自动依靠实例属性生成 repr
    """

    def __repr__(self) -> str:
        attrs = ", ".join(
            f"{k}={repr(v)}" for k, v in self.__dict__.items() if not k.startswith("_")
        )
        if len(attrs) >= 100:
            attrs = attrs[:100] + "..."
        return f"{self.__class__.__name__}({attrs})"


class LocateMixin:
    def __new__(cls, *_args: Any, **_kwargs: Any) -> Self:
        obj = super().__new__(cls)
        obj.__obj_location__ = obj.__location_init__()  # type: ignore[attr-defined]
        return obj

    def __init__(self) -> None:
        self.__obj_location__: tuple[str, str, int]

    @staticmethod
    def __location_init__() -> tuple[str, str, int]:
        frame = inspect.currentframe()
        while frame:
            if frame.f_code.co_name == "<module>":
                return (
                    frame.f_globals["__name__"],
                    frame.f_globals["__file__"],
                    frame.f_lineno,
                )
            frame = frame.f_back

        return ("<unknown module>", "<unknown file>", -1)

    @property
    def __obj_module__(self) -> str:
        return self.__obj_location__[0]

    @property
    def __obj_file__(self) -> str:
        return self.__obj_location__[1]

    @property
    def __obj_line__(self) -> int:
        return self.__obj_location__[2]


class HookMixin(Generic[HookEnumT]):
    """hook 混合类

    继承后可注册 hook
    """

    def __init__(self, hook_type: type[HookEnumT], hook_tag: str | None = None):
        """实例化一个 hook 混合类

        :param hook_type: hook 阶段的枚举类型
        :param hook_tag: 在日志信息中显示的 tag
        """
        super().__init__()
        self._hook_bus = HookBus[HookEnumT](hook_type, hook_tag)
        self.__repeatable_hook_types__: set[HookEnumT] = set()

    def __mark_repeatable_hooks__(self, *types: HookEnumT) -> None:
        for t in types:
            self.__repeatable_hook_types__.add(t)

    def get_hook_evoke_time(self, hook_type: HookEnumT) -> float:
        """获取指定 hook 最后一次触发的时间戳（秒）

        若从未触发过，返回 -1

        :param hook_type: hook 类型
        :return: 触发时间
        """
        return self._hook_bus.get_evoke_time(hook_type)

    def on(
        self, *periods: HookEnumT
    ) -> Callable[[SyncOrAsyncCallable[P, None]], AsyncCallable[P, None]]:
        """注册一个 hook

        :param periods: 要绑定的 hook 类型
        :return: 装饰器
        """

        def hook_register_wrapped(
            func: SyncOrAsyncCallable[P, None],
        ) -> AsyncCallable[P, None]:
            f = to_async(func)
            for type in periods:
                once = type not in self.__repeatable_hook_types__
                self._hook_bus.register(type, func, once)
            return f

        return hook_register_wrapped
