import warnings
from functools import wraps

from typing_extensions import Any, Callable, Iterable, ParamSpec, TypeVar, cast, overload

T = TypeVar("T", default=Any)
P = ParamSpec("P", default=Any)

# 以下代码，由 websockets.imports 模块源代码修改而来
# 原始版权 © Aymeric Augustin and contributors
# 原始许可：https://github.com/python-websockets/websockets/blob/main/LICENSE


def import_name(name: str, source: str, namespace: dict[str, Any]) -> Any:
    level = 0
    while source[level] == ".":
        level += 1
        if level >= len(source):
            raise ImportError("importing from parent isn't supported")
    module = __import__(source[level:], namespace, None, [name], level)
    return getattr(module, name)


def lazy_import(
    mod_globals: dict[str, Any],
    map: dict[str, tuple[str, ...]],
    deprecations: dict[str, tuple[tuple[str, str], ...]],
) -> None:
    # 不公开给用户，仅 melobot 内部使用
    mapping: dict[str, str] = {}
    for location, names in map.items():
        for name in names:
            mapping[name] = location

    deprecated_dic: dict[str, tuple[str, str]] = {}
    for location, pairs in deprecations.items():
        for name, ver in pairs:
            deprecated_dic[name] = (location, ver)

    mod_globals_set = set(mod_globals)
    mapping_set = set(mapping)
    deprecated_set = set(deprecated_dic)

    if mod_globals_set & mapping_set:
        raise ValueError("原始模块与延迟加载项有冲突的命名")
    if mod_globals_set & deprecated_set:
        raise ValueError("原始模块与弃用项有冲突的命名")
    if mapping_set & deprecated_set:
        raise ValueError("延迟加载项与弃用项有冲突的命名")

    mod_name = mod_globals["__name__"]

    def __getattr__(name: str) -> Any:
        try:
            location = mapping[name]
        except KeyError:
            pass
        else:
            return import_name(name, location, mod_globals)

        try:
            location, ver = deprecated_dic[name]
        except KeyError:
            pass
        else:
            warnings.simplefilter("always", DeprecationWarning)
            warnings.warn(
                f"{mod_name}.{name} 现以弃用，将于 {ver} 版本移除",
                category=DeprecationWarning,
                stacklevel=2,
            )
            warnings.simplefilter("default", DeprecationWarning)
            return import_name(name, location, mod_globals)

        raise AttributeError(f"module {mod_name!r} has no attribute {name!r}")

    def __dir__() -> Iterable[str]:
        return sorted(mod_globals_set | mapping_set | deprecated_set)

    mod_globals["__getattr__"] = __getattr__
    mod_globals["__dir__"] = __dir__


# --------------------------------------------------------------------------


class LazyLoader:
    def __init__(
        self,
        namespace: dict[str, Any],
        location: str,
        item: str | None = None,
        alias: str | None = None,
    ) -> None:
        self.item = item
        self.alias = alias
        self.location = location
        if self.location.startswith("."):
            raise ValueError(f"延迟加载不支持 {location!r} 中的相对引用语义")
        self.loc_parts = location.split(".")
        self.namespace = namespace
        self._value: Any

        if self.alias is not None:
            self.namespace[self.alias] = self
        elif self.item is None:
            self.namespace[self.loc_parts[0]] = self
        else:
            self.namespace[self.item] = self

    def __repr__(self) -> str:
        statement = ""
        if self.item is None:
            statement += f"import {self.location}"
        else:
            statement += f"from {self.location} import {self.item}"
        if self.alias is not None:
            statement += f" as {self.alias}"
        return f"{self.__class__.__name__}(equation={statement!r})"

    def _load(self) -> None:
        module = __import__(
            self.location, self.namespace, None, [self.item] if self.item is not None else ()
        )

        if self.item is None:
            if self.alias is None:
                self.namespace[self.loc_parts[0]] = self._value = module
            else:
                if len(self.loc_parts) > 1:
                    node = module
                    idx = 1
                    while idx < len(self.loc_parts):
                        node = getattr(node, self.loc_parts[idx])
                        idx += 1
                    module = node
                self.namespace[self.alias] = self._value = module
            return

        obj = getattr(module, self.item)
        if self.alias is None:
            self.namespace[self.item] = self._value = obj
        else:
            self.namespace[self.alias] = self._value = obj

    def __getattr__(self, name: str) -> Any:
        self._load()
        return getattr(self._value, name)


def lazy_load(
    namespace: dict[str, Any], location: str, item: str | None = None, alias: str | None = None
) -> str:
    return repr(LazyLoader(namespace, location, item, alias))


_SINGLETON_OBJ_MAP: dict[Any, Any] = {}
_SINGLETON_FACTORY_MAP: dict[Any, Any] = {}


@overload
def singleton(cls: type[T]) -> type[T]: ...
@overload
def singleton(cls: Callable[P, T]) -> Callable[P, T]: ...


def singleton(cls: type[T] | Callable[P, T]) -> type[T] | Callable[P, T]:
    """单例装饰器

    :param cls: 需要被单例化的可调用对象
    :return: 需要被单例化的可调用对象
    """

    @wraps(cls)
    def singleton_wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        if cls not in _SINGLETON_OBJ_MAP:
            obj = _SINGLETON_OBJ_MAP[cls] = cls(*args, **kwargs)
            _SINGLETON_FACTORY_MAP[obj] = cls
        return cast(T, _SINGLETON_OBJ_MAP[cls])

    return singleton_wrapped


def singleton_clear(obj: Any) -> None:
    """清除已经缓存的单例

    :param obj: 单例化得到的对象
    """
    if obj not in _SINGLETON_FACTORY_MAP:
        raise ValueError(
            f"{obj} 不在单例装饰器的记录中。"
            "它可能不是单例对象，或产生此单例的类或可调用对象已清空单例缓存"
        )
    callable_or_cls = _SINGLETON_FACTORY_MAP.pop(obj)
    _SINGLETON_OBJ_MAP.pop(callable_or_cls)
