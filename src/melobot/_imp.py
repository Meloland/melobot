import sys
import zipimport
from importlib._bootstrap_external import PathFinder as _PathFinder
from importlib._bootstrap_external import (
    _get_supported_file_loaders,
    _NamespaceLoader,
    _NamespacePath,
)
from importlib.abc import Loader, MetaPathFinder
from importlib.machinery import ModuleSpec, all_suffixes
from importlib.util import module_from_spec, spec_from_file_location
from os import PathLike
from pathlib import Path
from types import ModuleType
from typing import Any, Sequence, cast

import pkg_resources

from .exceptions import DynamicImpError
from .utils import singleton

ALL_EXTS = tuple(all_suffixes())
NAMESPACE_PKG_TAG = "__melobot_namespace__"


class _NestedQuickExit(BaseException): ...


@singleton
class SpecFinder(MetaPathFinder):

    def find_spec(
        self,
        fullname: str,
        paths: Sequence[str] | None,
        target: ModuleType | None = None,  # pylint: disable=unused-argument
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
        # The spec finding according PEP420: https://peps.python.org/pep-0420/#specification
        try:
            for entry in paths:
                entry_path = Path(entry)
                zip_file_path = entry_path.joinpath(f"{name}.zip")
                dir_path = entry_path.joinpath(name)
                pkg_init_path = dir_path.joinpath("__init__.py")

                if pkg_init_path.exists():
                    mod_path = pkg_init_path
                    submod_locs = [str(dir_path.resolve())]
                    raise _NestedQuickExit

                for ext in ALL_EXTS:
                    _mod_path = entry_path.joinpath(f"{name}{ext}")
                    if _mod_path.exists():
                        mod_path = _mod_path
                        submod_locs = None
                        raise _NestedQuickExit

                if zip_file_path.exists():
                    spec = zipimport.zipimporter(str(zip_file_path)).find_spec(
                        fullname, target
                    )
                    assert spec is not None
                    assert spec.loader is not None
                    spec.loader = ModuleLoader(
                        fullname,
                        zip_file_path,
                        sys_cache,
                        load_cache,
                        pre_sys_len,
                        pre_cache_len,
                        spec.loader,
                    )
                    return spec

                if dir_path.exists() and dir_path.is_dir():
                    dir_path_str = str(dir_path.resolve())
                    submod_locs = _NamespacePath(
                        fullname,
                        [dir_path_str],
                        _PathFinder()._get_spec,  # pylint: disable=protected-access
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
                            _NamespaceLoader(fullname, [dir_path_str], submod_locs),
                        ),
                        submodule_search_locations=submod_locs,
                    )
                    assert spec is not None
                    spec.has_location = False
                    spec.origin = None
                    setattr(spec, NAMESPACE_PKG_TAG, True)
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
        # 对应有 __init__.py 的包模块
        if path.parts[-1] == "__init__.py":
            path = path.parent
        return self._caches.get(path)

    def set_cache(self, name: str, mod: ModuleType) -> None:
        if (
            mod in self._caches.values()
            or name in sys.stdlib_module_names
            or not hasattr(mod, "__file__")
        ):
            return

        # __file__ 存在且不为空，可能包或任意可被加载的文件，包对应 __init__.py，应该转换为不包含 __init__.py 后缀的形式
        if mod.__file__ is not None:
            fp = Path(mod.__file__)
            if fp.parts[-1] == "__init__.py":
                self._caches[fp.parent] = mod
            else:
                self._caches[fp] = mod
        # 若 __file__ 为空则有 __path__，对应无 __init__.py 的包
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
        self.cacher = ModuleCacher()
        self.fullname = fullname
        self.fp = fp
        self.use_sys_cache = sys_cache
        self.use_load_cache = load_cache
        self.pre_sys_len = pre_sys_len
        self.pre_cache_len = pre_cache_len

        self.inner_loader: Loader | None = inner_loader
        if inner_loader is not None:
            return

        for loader_class, suffixes in _get_supported_file_loaders():
            if str(fp).endswith(tuple(suffixes)):
                loader = loader_class(fullname, str(fp))  # pylint: disable=not-callable
                self.inner_loader = loader
                break

    def create_module(self, spec: ModuleSpec) -> ModuleType | None:
        mod = None
        if self.use_load_cache:
            mod = self.cacher.get_cache(self.fp)
        if mod is None and self.inner_loader is not None:
            mod = self.inner_loader.create_module(spec)
        return mod

    def exec_module(self, mod: ModuleType) -> None:
        if self.cacher.has_cache(mod):
            pass
        else:
            if self.inner_loader is not None:
                if self.use_sys_cache:
                    sys.modules[self.fullname] = mod

                try:
                    self.inner_loader.exec_module(mod)
                    if hasattr(mod.__spec__, NAMESPACE_PKG_TAG):
                        mod.__file__ = None
                except BaseException:
                    try:
                        del sys.modules[self.fullname]
                    except KeyError:
                        pass
                    raise

        if self.use_load_cache:
            self.cacher.set_cache(self.fullname, mod)

        if not self.use_load_cache:
            diff = self.cacher.get_len() - self.pre_cache_len
            if diff > 0:
                self.cacher.rm_lastn(diff)

        if not self.use_sys_cache:
            diff = len(sys.modules) - self.pre_sys_len
            if diff > 0:
                iter = reversed(sys.modules.keys())
                rm_names: list[str] = []
                for _ in range(diff):
                    rm_names.append(next(iter))
                for name in rm_names:
                    sys.modules.pop(name)

    def __getattr__(self, name: str) -> Any:
        if self.inner_loader is not None:
            return getattr(self.inner_loader, name)
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )


class Importer:
    @staticmethod
    def import_mod(
        name: str,
        path: str | PathLike[str] | None = None,
        sys_cache: bool = True,
        load_cache: bool = True,
    ) -> ModuleType:
        pre_sys_len = len(sys.modules)
        pre_cache_len = ModuleCacher().get_len()

        if path is not None:
            if load_cache:
                if (mod_cache := Importer.get_cache(Path(path))) is not None:
                    return mod_cache

            try:
                sep = name.rindex(".")
                Importer.import_mod(name[:sep], Path(path).parent, True, True)
            except ValueError:
                pass

        if sys_cache and name in sys.modules:
            return sys.modules[name]

        spec = SpecFinder().find_spec(
            name,
            (str(path),) if path is not None else None,
            sys_cache=sys_cache,
            load_cache=load_cache,
            pre_sys_len=pre_sys_len,
            pre_cache_len=pre_cache_len,
        )
        if spec is None:
            raise DynamicImpError(
                f"名为 {name} 的模块无法加载，指定的位置：{path}",
                name=name,
                path=str(path),
            )
        mod = module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        return mod

    @staticmethod
    def clear_cache() -> None:
        ModuleCacher().clear_cache()

    @staticmethod
    def get_cache(path: Path) -> ModuleType | None:
        return ModuleCacher().get_cache(path)


sys.meta_path.insert(0, SpecFinder())
pkg_resources.register_finder(SpecFinder, pkg_resources.find_on_path)
pkg_resources.register_loader_type(ModuleLoader, pkg_resources.DefaultProvider)
pkg_resources.register_namespace_handler(SpecFinder, pkg_resources.file_ns_handler)
