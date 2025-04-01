import warnings
from functools import wraps

from typing_extensions import Any, Callable, Iterable, ParamSpec, TypeVar, overload

T = TypeVar("T", default=Any)
P = ParamSpec("P", default=Any)

# 以下代码，由 websockets.imports 模块源代码修改而来
# 原始版权 © Aymeric Augustin and contributors
# 原始许可：https://github.com/python-websockets/websockets/blob/main/LICENSE


def import_name(name: str, source: str, namespace: dict[str, Any]) -> Any:
    level = 0
    while source[level] == ".":
        level += 1
        assert level < len(source), "importing from parent isn't supported"
    module = __import__(source[level:], namespace, None, [name], level)
    return getattr(module, name)


def lazy_import(
    mod_globals: dict[str, Any],
    map: dict[str, tuple[str, ...]],
    deprecations: dict[str, tuple[tuple[str, str], ...]],
) -> None:

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


@overload
def singleton(cls: type[T]) -> type[T]: ...
@overload
def singleton(cls: Callable[P, T]) -> Callable[P, T]: ...


def singleton(cls: type[T] | Callable[P, T]) -> type[T] | Callable[P, T]:
    """单例装饰器

    :param cls: 需要被单例化的可调用对象
    :return: 需要被单例化的可调用对象
    """
    obj_map = {}

    @wraps(cls)
    def singleton_wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        if cls not in obj_map:
            obj_map[cls] = cls(*args, **kwargs)
        return obj_map[cls]

    return singleton_wrapped
