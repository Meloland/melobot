import sys
import zipimport

if sys.version_info < (3, 11):
    from importlib._bootstrap_external import _NamespaceLoader
else:
    from importlib.machinery import NamespaceLoader as _NamespaceLoader

from importlib.abc import FileLoader, Loader, MetaPathFinder
from importlib.machinery import (
    BYTECODE_SUFFIXES,
    EXTENSION_SUFFIXES,
    SOURCE_SUFFIXES,
    ExtensionFileLoader,
    ModuleSpec,
)
from importlib.machinery import PathFinder as _PathFinder
from importlib.machinery import (
    SourceFileLoader,
    SourcelessFileLoader,
)
from importlib.util import module_from_spec, spec_from_file_location
from os import PathLike
from pathlib import Path
from types import ModuleType

from typing_extensions import Any, Sequence, cast

from ._lazy import singleton
from .exceptions import DynamicImpError, DynamicImpSpecEmpty

# 扩展名的优先级顺序非常重要
ALL_EXTS = tuple(EXTENSION_SUFFIXES + SOURCE_SUFFIXES + BYTECODE_SUFFIXES)
PKG_INIT_FILENAMES = tuple(f"__init__{ext}" for ext in ALL_EXTS)
EMPTY_PKG_TAG = "__melobot_namespace_pkg__"
ZIP_MODULE_TAG = "__melobot_zip_module__"


def _get_file_loaders() -> list[tuple[type[Loader], list[str]]]:
    extensions = (ExtensionFileLoader, EXTENSION_SUFFIXES)
    source = (SourceFileLoader, SOURCE_SUFFIXES)
    bytecode = (SourcelessFileLoader, BYTECODE_SUFFIXES)
    return [extensions, source, bytecode]


class _NestedQuickExit(BaseException): ...


@singleton
class SpecFinder(MetaPathFinder):
    def find_spec(
        self,
        fullname: str,
        paths: Sequence[str] | None,
        target: ModuleType | None = None,
        cache: bool = True,
    ) -> ModuleSpec | None:
        if fullname.startswith(_IMP_FALLBACKS):
            return None

        if paths is None:
            paths = sys.path
        if "." in fullname:
            *_, name = fullname.split(".")
        else:
            name = fullname

        mod_path: Path | None = None
        submod_locs: list[str] | None = None

        # 模块查找的优先级，遵循 PEP420: https://peps.python.org/pep-0420/#specification
        try:
            for entry in paths:
                entry_path = Path(entry)
                dir_path = entry_path.joinpath(name)
                pkg_init_paths = tuple(
                    dir_path.joinpath(filename) for filename in PKG_INIT_FILENAMES
                )

                # 带有 __init__.* 的包优先
                for pkg_init_path in pkg_init_paths:
                    if pkg_init_path.exists():
                        mod_path = pkg_init_path
                        submod_locs = [str(dir_path.resolve())]
                        raise _NestedQuickExit

                # 其次是各种可加载的文件
                for ext in ALL_EXTS:
                    _mod_path = entry_path.joinpath(f"{name}{ext}")
                    if _mod_path.exists():
                        mod_path = _mod_path
                        submod_locs = None
                        raise _NestedQuickExit

                # 再次是 zip 文件导入
                if entry_path.suffix == ".zip" and entry_path.exists():
                    zip_importer = zipimport.zipimporter(str(entry_path))
                    spec = zip_importer.find_spec(fullname, target)

                    if spec is not None:
                        if spec.origin is None or spec.origin == "":
                            raise DynamicImpError(
                                f"zip file from {entry_path}, module named {fullname} from {target}, "
                                "failed to get spec origin",
                                name=fullname,
                                path=entry_path.as_posix(),
                            )
                        if spec.loader is None:
                            raise DynamicImpError(
                                f"zip file from {entry_path}, module named {fullname} from {target}, "
                                "spec has no loader",
                                name=fullname,
                                path=entry_path.as_posix(),
                            )

                        spec.loader = ModuleLoader(
                            fullname, Path(spec.origin).resolve(), cache, spec.loader
                        )
                        setattr(spec, ZIP_MODULE_TAG, True)
                        return spec

                # 没有 __init__.* 的包最后查找，spec 设置为与内置导入兼容的命名空间包格式
                if dir_path.exists() and dir_path.is_dir():
                    dir_path_str = str(dir_path.resolve())
                    loader = cast(
                        Loader,
                        _NamespaceLoader(
                            fullname,
                            [dir_path_str],
                            _PathFinder._get_spec,  # type: ignore[attr-defined]
                        ),
                    )
                    spec = spec_from_file_location(
                        fullname,
                        dir_path_str,
                        loader=ModuleLoader(fullname, dir_path, cache, loader),
                        submodule_search_locations=loader._path,  # type: ignore[attr-defined]
                    )

                    if spec is None:
                        raise DynamicImpSpecEmpty(
                            f"package from {dir_path} without __init__ file create spec failed",
                            name=fullname,
                            path=dir_path.as_posix(),
                        )

                    spec.has_location = False
                    spec.origin = None
                    setattr(spec, EMPTY_PKG_TAG, True)
                    return spec

        except _NestedQuickExit:
            pass

        if mod_path is None and submod_locs is None:
            return None

        mod_path = cast(Path, mod_path).resolve()
        return spec_from_file_location(
            fullname,
            str(mod_path),
            loader=ModuleLoader(fullname, mod_path, cache),
            submodule_search_locations=submod_locs,
        )


@singleton
class ModuleCacher:
    def __init__(self) -> None:
        self._caches: dict[Path, ModuleType] = {}
        self.sync_all_cache()

    # 此处不过多考虑与 sys.modules 的同步问题,
    # 喜爱 hack sys.modules 以至于不兼容的模块，让用户使用导入回退来处理

    # 严格来说，导入缓存应该考虑线程安全问题。
    # 但无论是内置 import 行为（import 语句，__import__ 等），
    # 还是 mb 的动态导入，只要不在非主线程中运行，实际上都不会存在问题。
    # 只需鼓励用户只进行主线程导入即可，这也是十分合理的编程规范。
    # 极少的多线程导入用例，不值得付出加锁的性能代价

    def has_cache(self, mod: ModuleType) -> bool:
        return mod in self._caches.values()

    def get_cache(self, path: Path) -> ModuleType | None:
        # 对应有 __init__.* 的包模块
        if path.parts[-1] in PKG_INIT_FILENAMES:
            path = path.parent
        return self._caches.get(path)

    def set_cache(self, name: str, mod: ModuleType) -> None:
        if (
            mod in self._caches.values()
            or name in sys.stdlib_module_names
            or not hasattr(mod, "__file__")
        ):
            return

        # __file__ 存在且不为空，可能包或任意可被加载的文件
        if mod.__file__ is not None:
            fp = Path(mod.__file__)
            if fp.parts[-1] in PKG_INIT_FILENAMES:
                self._caches[fp.parent] = mod
            else:
                self._caches[fp] = mod
        # 若 __file__ 为空则有 __path__，对应无 __init__.* 的包
        else:
            self._caches[Path(mod.__path__[0])] = mod

    def rm_cache(self, path: Path) -> None:
        # 对应有 __init__.* 的包模块
        if path.parts[-1] in PKG_INIT_FILENAMES:
            path = path.parent
        self._caches.pop(path)

    def sync_all_cache(self) -> None:
        self._caches.clear()
        for name, mod in sys.modules.items():
            self.set_cache(name, mod)


class ModuleLoader(Loader):
    def __init__(
        self,
        fullname: str,
        fp: Path,
        cache: bool,
        inner_loader: Loader | None = None,
    ) -> None:
        super().__init__()
        # 避免在 self.__getattr__() 反射时重名
        self.mb_cacher = ModuleCacher()
        self.mb_fullname = fullname
        self.mb_fp = fp
        self.mb_cache = cache
        self.mb_inner_loader: Loader | None = inner_loader

        if inner_loader is not None:
            return

        for loader_cls, suffixes in _get_file_loaders():
            if fp.resolve().suffix in suffixes:
                loader_cls = cast(type[FileLoader], loader_cls)
                # 使用 str 转化为平台偏好的路径格式（特别是避免在特定 win 版本上不兼容）
                loader = loader_cls(fullname, str(fp))
                self.mb_inner_loader = loader
                break

    def create_module(self, spec: ModuleSpec) -> ModuleType | None:
        mod = None
        if self.mb_cache:
            mod = self.mb_cacher.get_cache(self.mb_fp)
        if mod is not None and mod.__name__ not in sys.modules:
            # 模块有缓存，但不在 sys.modules 中，说明外部手动移除。
            # 此时要同步删除缓存条目，让行为符合外部预期。
            # 对 sys.modules 的其他修改不需要兼容（极少出现），实在需要就用导入回退
            mod = None
            self.mb_cacher.rm_cache(self.mb_fp)
        if mod is None and self.mb_inner_loader is not None:
            mod = self.mb_inner_loader.create_module(spec)
        return mod

    def exec_module(self, mod: ModuleType) -> None:
        if not self.mb_cacher.has_cache(mod) and self.mb_inner_loader is not None:
            # 遵循先记录原则，防止 exec_module 发起的某些递归导入出现错误
            if self.mb_cache:
                sys.modules[self.mb_fullname] = mod

            try:
                # 设置为与内置导入机制兼容的模式
                if hasattr(mod.__spec__, EMPTY_PKG_TAG):
                    mod.__file__ = None
                self.mb_inner_loader.exec_module(mod)
            except BaseException:
                try:
                    if self.mb_cache:
                        del sys.modules[self.mb_fullname]
                except KeyError:
                    pass
                raise

        # 若 inner_loader 为空，则是纯粹的命名空间包（没有 __init__.* 的包模块）
        # 也就不需要任何实质性的 exec_module 过程
        if self.mb_cache:
            self.mb_cacher.set_cache(self.mb_fullname, mod)

    def __getattr__(self, name: str) -> Any:
        # 直接使用反射，而不是更复杂的继承方案
        # inner_loader 实现了必要的 内省接口、importlib.resources 接口
        if self.mb_inner_loader is not None:
            return getattr(self.mb_inner_loader, name)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")


_IMP_FALLBACKS: tuple[str, ...] = ()
_IMP_FALLBACK_SET: set[str] = set()


class Importer:
    @staticmethod
    def import_mod(
        name: str, path: str | PathLike[str] | None = None, cache: bool = True
    ) -> ModuleType:
        """动态导入一个模块，非线程安全

        :param name: 模块名
        :param path: 在何处查找模块，为空则按照默认规则查找
        :param cache: 是否在 `sys.modules` 中缓存模块
        :return: 模块
        """
        if name.startswith(_IMP_FALLBACKS):
            raise DynamicImpError(
                f"模块 {name} 被标记为回退默认导入机制，无法使用动态导入",
                name=name,
                path=str(path),
            )

        if path is not None:
            try:
                sep = name.rindex(".")
            except ValueError:
                pass
            else:
                Importer.import_mod(name[:sep], Path(path).parent)

        if cache and name in sys.modules:
            return sys.modules[name]

        spec = SpecFinder().find_spec(name, (str(path),) if path is not None else None, cache=cache)
        if spec is None:
            raise DynamicImpSpecEmpty(
                f"名为 {name} 的模块无法加载，指定的位置：{path}",
                name=name,
                path=str(path),
            )

        mod = module_from_spec(spec)
        if spec.loader is None:
            raise DynamicImpError(
                f"module named {name} and path from {path} has no loader", name=name, path=str(path)
            )
        spec.loader.exec_module(mod)
        return mod

    @staticmethod
    def add_fallback(*names: str) -> None:
        global _IMP_FALLBACKS
        for name in names:
            _IMP_FALLBACK_SET.add(name)
        _IMP_FALLBACKS = tuple(_IMP_FALLBACK_SET)

    @staticmethod
    def clear_cache() -> None:
        ModuleCacher().sync_all_cache()

    @staticmethod
    def get_cache(path: Path) -> ModuleType | None:
        return ModuleCacher().get_cache(path)


sys.meta_path.insert(0, SpecFinder())

# 兼容 pkg_resources 的资源获取操作
# 但此模块于 3.12 删除，因此前向版本不再兼容
if sys.version_info < (3, 12):
    # 部分构建（例如 uv 发行的构建）可能已经缺失 pkg_resources
    try:
        import pkg_resources  # type: ignore[import-untyped]
    except ModuleNotFoundError:
        pass
    else:

        def _union_provider(mod: Any) -> pkg_resources.NullProvider:
            if hasattr(mod.__spec__, ZIP_MODULE_TAG):
                return pkg_resources.ZipProvider(mod)
            return pkg_resources.DefaultProvider(mod)

        pkg_resources.register_loader_type(ModuleLoader, cast(type, _union_provider))
        pkg_resources.register_namespace_handler(SpecFinder, pkg_resources.file_ns_handler)


def add_import_fallback(*names: str) -> None:
    """添加未导入模块或包的导入回退，非线程安全

    绝大多数情况下，melobot 都能处理好导入行为。
    但在极少数情况下，某些包或模块可能需要回退到默认的导入机制

    使用此方法，将模块名以 `names` 起始的模块或包标记为需要回退

    :param names: 需要回退的模块或包名称的起始字符串
    """
    Importer.add_fallback(*names)
