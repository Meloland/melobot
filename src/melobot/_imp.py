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

from .exceptions import DynamicImpSpecEmpty
from .utils.common import singleton

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
        sys_cache: bool = True,
        load_cache: bool = True,
        pre_sys_len: int = -1,
        pre_cache_len: int = -1,
    ) -> ModuleSpec | None:
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
                        assert spec.origin is not None and spec.origin != "", (
                            f"zip file from {entry_path}, module named {fullname} from {target}, "
                            "failed to get spec origin"
                        )
                        assert spec.loader is not None, (
                            f"zip file from {entry_path}, module named {fullname} from {target}, "
                            "spec has no loader"
                        )
                        spec.loader = ModuleLoader(
                            fullname,
                            Path(spec.origin).resolve(),
                            sys_cache,
                            load_cache,
                            pre_sys_len,
                            pre_cache_len,
                            spec.loader,
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
                        loader=ModuleLoader(
                            fullname,
                            dir_path,
                            sys_cache,
                            load_cache,
                            pre_sys_len,
                            pre_cache_len,
                            loader,
                        ),
                        submodule_search_locations=loader._path,  # type: ignore[attr-defined]
                    )
                    assert (
                        spec is not None
                    ), f"package from {dir_path} without __init__ file create spec failed"
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
            loader=ModuleLoader(
                fullname, mod_path, sys_cache, load_cache, pre_sys_len, pre_cache_len
            ),
            submodule_search_locations=submod_locs,
        )


@singleton
class ModuleCacher:
    def __init__(self) -> None:
        self._caches: dict[Path, ModuleType] = {}
        self.clear_cache()

    def get_len(self) -> int:
        return len(self._caches)

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

    def rm_lastn(self, n: int) -> None:
        iter = reversed(self._caches.keys())
        rm_paths: list[Path] = []
        for _ in range(n):
            rm_paths.append(next(iter))
        for p in rm_paths:
            self._caches.pop(p)

    def clear_cache(self) -> None:
        self._caches.clear()
        for name, mod in sys.modules.items():
            self.set_cache(name, mod)


class ModuleLoader(Loader):
    def __init__(
        self,
        fullname: str,
        fp: Path,
        sys_cache: bool,
        load_cache: bool,
        pre_sys_len: int = -1,
        pre_cache_len: int = -1,
        inner_loader: Loader | None = None,
    ) -> None:
        super().__init__()
        # 避免在 self.__getattr__() 反射时重名
        self.melobot_cacher = ModuleCacher()
        self.melobot_fullname = fullname
        self.melobot_fp = fp
        self.melobot_sys_cache = sys_cache
        self.melobot_load_cache = load_cache
        self.melobot_pre_sys_len = pre_sys_len
        self.melobot_pre_cache_len = pre_cache_len

        self.melobot_inner_loader: Loader | None = inner_loader
        if inner_loader is not None:
            return

        for loader_cls, suffixes in _get_file_loaders():
            if str(fp).endswith(tuple(suffixes)):
                loader_cls = cast(type[FileLoader], loader_cls)
                loader = loader_cls(fullname, str(fp))
                self.melobot_inner_loader = loader
                break

    def create_module(self, spec: ModuleSpec) -> ModuleType | None:
        mod = None
        if self.melobot_load_cache:
            mod = self.melobot_cacher.get_cache(self.melobot_fp)
        if mod is None and self.melobot_inner_loader is not None:
            mod = self.melobot_inner_loader.create_module(spec)
        return mod

    def exec_module(self, mod: ModuleType) -> None:
        if not self.melobot_cacher.has_cache(mod) and self.melobot_inner_loader is not None:
            # 遵循先记录原则，防止 exec_module 发起的某些递归导入出现错误
            if self.melobot_sys_cache:
                sys.modules[self.melobot_fullname] = mod

            try:
                self.melobot_inner_loader.exec_module(mod)
                # 设置为与内置导入机制兼容的模式
                if hasattr(mod.__spec__, EMPTY_PKG_TAG):
                    mod.__file__ = None
            except BaseException:
                try:
                    del sys.modules[self.melobot_fullname]
                except KeyError:
                    pass
                raise
        # 若 inner_loader 为空，则是纯粹的命名空间包（没有 __init__.* 的包模块）
        # 也就不需要任何实质性的 exec_module 过程

        if self.melobot_load_cache:
            self.melobot_cacher.set_cache(self.melobot_fullname, mod)

        if not self.melobot_load_cache:
            diff = self.melobot_cacher.get_len() - self.melobot_pre_cache_len
            if diff > 0:
                self.melobot_cacher.rm_lastn(diff)

        if not self.melobot_sys_cache:
            diff = len(sys.modules) - self.melobot_pre_sys_len
            if diff > 0:
                iter = reversed(sys.modules.keys())
                rm_names: list[str] = []
                for _ in range(diff):
                    rm_names.append(next(iter))
                for name in rm_names:
                    sys.modules.pop(name)

    def __getattr__(self, name: str) -> Any:
        # 直接使用反射，而不是更复杂的继承方案
        # inner_loader 实现了必要的 内省接口、importlib.resources 接口
        if self.melobot_inner_loader is not None:
            return getattr(self.melobot_inner_loader, name)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")


class Importer:
    @staticmethod
    def import_mod(
        name: str,
        path: str | PathLike[str] | None = None,
        sys_cache: bool = True,
        mb_cache: bool = True,
    ) -> ModuleType:
        """动态导入一个模块

        :param name: 模块名
        :param path: 在何处查找模块，为空则按照默认规则查找
        :param sys_cache: 是否加载后在 `sys.modules` 中缓存
        :param load_cache: 是否加载后在 melobot 模块缓存器中缓存
        :return: 模块
        """
        # 必须先获取，后续可能运行的递归将会影响序列长度
        pre_sys_len = len(sys.modules)
        pre_cache_len = ModuleCacher().get_len()

        if path is not None:
            try:
                sep = name.rindex(".")
            except ValueError:
                pass
            else:
                Importer.import_mod(name[:sep], Path(path).parent, True, True)

        if sys_cache and name in sys.modules:
            return sys.modules[name]

        spec = SpecFinder().find_spec(
            name,
            (str(path),) if path is not None else None,
            sys_cache=sys_cache,
            load_cache=mb_cache,
            pre_sys_len=pre_sys_len,
            pre_cache_len=pre_cache_len,
        )
        if spec is None:
            raise DynamicImpSpecEmpty(
                f"名为 {name} 的模块无法加载，指定的位置：{path}",
                name=name,
                path=str(path),
            )

        mod = module_from_spec(spec)
        assert spec.loader is not None, f"module named {name} and path from {path} has no loader"
        spec.loader.exec_module(mod)
        return mod

    @staticmethod
    def clear_cache() -> None:
        ModuleCacher().clear_cache()

    @staticmethod
    def get_cache(path: Path) -> ModuleType | None:
        return ModuleCacher().get_cache(path)


sys.meta_path.insert(0, SpecFinder())

# 兼容 pkg_resources 的资源获取操作
# 但此模块于 3.12 删除，因此前向版本不再兼容
if sys.version_info < (3, 12):
    # 部分构建可能已经缺失 pkg_resources
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
