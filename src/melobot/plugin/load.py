import sys
from os import PathLike
from pathlib import Path
from types import ModuleType

from typing_extensions import Any, Iterable, cast

from .._imp import ALL_EXTS, Importer
from .._lazy import singleton
from ..ctx import BotCtx
from ..exceptions import DynamicImpSpecEmpty, PluginLoadError
from ..log.reflect import logger
from .base import Plugin, PluginPlanner


def plugin_get_attr(p_name: str, name: str, excepts: Iterable[str]) -> Any:
    if name in excepts or name.startswith("_"):
        raise AttributeError
    obj = BotCtx().get().ipc_manager.get(p_name, name)
    if obj.static:
        return obj.get()
    return obj


P_PLANNER_ATTR = "__plugin_planner__"
P_INFO_ATTR = "__plugin_info__"
_MODULE_EXTS = ALL_EXTS


@singleton
class PluginLoader:
    def __init__(self) -> None:
        self._dir_caches: dict[str, Path] = {}

    def load(
        self, plugin: ModuleType | str | PathLike[str] | PluginPlanner, load_depth: int
    ) -> tuple[Plugin, bool]:
        if isinstance(plugin, PluginPlanner):
            p_name = f"_DynamicPlugin_0x{id(plugin):0x}"
            return self._build_dynamic(p_name, plugin)

        if (
            isinstance(plugin, str)
            and not plugin.endswith(_MODULE_EXTS)
            and not Path(plugin).exists()
        ):
            try:
                tmp_mod = Importer.import_mod(plugin)
                plugin = tmp_mod
            except DynamicImpSpecEmpty:
                pass

        if isinstance(plugin, ModuleType):
            p_dir = self._get_mod_plugin_dir(plugin)
        else:
            p_dir = Path(plugin)
        try:
            p_dir = p_dir.resolve(strict=True)
        except FileNotFoundError:
            raise PluginLoadError(f"插件目录不存在，无法加载。对应插件：{p_dir}") from None

        p_name = p_dir.parts[-1]
        logger.debug(f"尝试加载来自 {p_dir!r} 的插件：{p_name}")
        return self._build_from_dir(p_name, p_dir, load_depth)

    def _build_dynamic(self, p_name: str, planner: PluginPlanner) -> tuple[Plugin, bool]:
        return self._create_plugin(p_name, planner, None)

    def _build_from_dir(self, p_name: str, p_dir: Path, load_depth: int) -> tuple[Plugin, bool]:
        if p_name in sys.stdlib_module_names:
            raise PluginLoadError(
                f"尝试加载的插件 {p_name} 与 Python 内置模块重名，"
                f"请修改名称（修改插件目录名）。对应插件：{p_dir}"
            )
        if not p_dir.joinpath("__plugin__.py").exists():
            raise PluginLoadError(f"插件目录下不存在 __plugin__.py，无法加载。对应插件：{p_dir}")
        if p_name in self._dir_caches and p_dir.resolve() != self._dir_caches[p_name]:
            raise PluginLoadError(
                f"试图加载一个与已加载插件同名的插件，名称：{p_name}，尝试加载的插件：{p_dir}"
            )

        p_mod = Importer.get_cache(p_dir)
        if p_mod is not None:
            p_entry_mod_name = f"{p_mod.__name__}.__plugin__"
        else:
            prefix = ".".join(p_dir.parts[-load_depth:])
            p_entry_mod_name = f"{prefix}.__plugin__"
        entry = Importer.import_mod(p_entry_mod_name, p_dir)

        if not hasattr(entry, P_PLANNER_ATTR):
            for k in dir(entry):
                val = getattr(entry, k)
                if isinstance(val, PluginPlanner):
                    setattr(entry, P_PLANNER_ATTR, val)
                    break
            else:
                raise PluginLoadError(
                    f"__plugin__.py 未实例化 {PluginPlanner.__name__}，无法加载。"
                    f"对应插件：{p_dir}"
                )

        planner = cast(PluginPlanner, getattr(entry, P_PLANNER_ATTR))
        p, is_repeat = self._create_plugin(p_name, planner, entry)
        if not is_repeat:
            self._dir_caches[p_name] = p_dir.resolve()
            setattr(entry, P_INFO_ATTR, planner.info)
        return p, is_repeat

    def _create_plugin(
        self, p_name: str, planner: PluginPlanner, entry: ModuleType | None
    ) -> tuple[Plugin, bool]:
        if planner._built:
            p = planner._plugin
            logger.debug(f"插件 {p.name} 已加载，重复加载将被跳过")
            return p, True

        if entry is not None:
            p_dir = self._get_mod_plugin_dir(entry).resolve()
            self._auto_import(p_name, entry.__name__, p_dir, planner.auto_import)

        planner._pname = p_name
        planner._hook_bus.set_tag(p_name)
        p = planner._plugin = Plugin(planner)
        planner._built = True
        return p, False

    def _auto_import(
        self, p_name: str, p_entry_mod_name: str, p_dir: Path, paths: Iterable[str] | bool
    ) -> None:
        if paths is False:
            return
        if paths is True:
            paths = map(str, p_dir.glob("**/*.py"))

        p_mod_name = p_entry_mod_name.rsplit(".", maxsplit=1)[0]
        for path_str in paths:
            ext = next((ext for ext in _MODULE_EXTS if path_str.endswith(ext)), None)
            if ext is None:
                raise PluginLoadError(
                    f"插件 {p_name} 的自动导入列表中，{path_str!r} 不是可加载的模块"
                )

            path = Path(path_str)
            if not path.is_absolute():
                path = p_dir.joinpath(path)
            try:
                path = path.resolve().relative_to(p_dir)
            except ValueError:
                raise PluginLoadError(
                    f"插件 {p_name} 自动导入时，以下路径无法计算相对导入关系：{path_str!r}"
                )

            if path.name == f"__plugin__{ext}":
                continue
            elif path.name == f"__init__{ext}":
                path = path.parent
                parts = path.parts
            else:
                parts = (*path.parts[:-1], path.parts[-1].removesuffix(ext))

            mod_name = f"{p_mod_name}.{'.'.join(parts)}"
            # 恢复绝对路径，准备加载
            path = p_dir.joinpath(path).resolve()
            Importer.import_mod(mod_name, path.parent.as_posix())

    def _get_mod_plugin_dir(self, mod: ModuleType) -> Path:
        if mod.__file__ is None:
            p_dir = Path(mod.__path__[0])
        else:
            p_dir = Path(mod.__file__).parent
        return p_dir
