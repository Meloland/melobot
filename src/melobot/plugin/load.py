import importlib.resources
import re
import sys
from contextlib import ExitStack
from inspect import getabsfile
from os import PathLike, listdir, remove
from pathlib import Path
from time import time
from types import ModuleType

from typing_extensions import Any, Callable, Iterable, cast

from .._imp import ALL_EXTS, Importer
from .._lazy import singleton
from ..ctx import BotCtx
from ..exceptions import DynamicImpSpecEmpty, PluginAutoGenError, PluginLoadError
from ..log.reflect import logger
from .base import Plugin, PluginPlanner
from .ipc import AsyncShare, SyncShare


def plugin_get_attr(p_name: str, name: str, excepts: Iterable[str]) -> Any:
    if name in excepts or name.startswith("_"):
        raise AttributeError
    obj = BotCtx().get().ipc_manager.get(p_name, name)
    if obj.static:
        return obj.get()
    return obj


_AUTOGEN_COMMENT = r"""# This file is @generated by melobot cli.
# It is not intended for manual editing.
"""


class PluginInitHelper:
    _BASE_INIT_PY_STR = (
        importlib.resources.files(__package__)
        .joinpath("__init__.template.py")
        .read_text(encoding="utf-8")
    )

    @staticmethod
    def _get_init_py_str(p_planner: PluginPlanner) -> str:
        output = re.sub(
            r"_VAR(\d+)",
            lambda matched: f"_{int(time()):#x}{matched.group(1)}",
            PluginInitHelper._BASE_INIT_PY_STR,
        )

        output = f'{output}__version__ = "{p_planner.version}"\n'
        if p_planner.info.author != "":
            output = f'{output}__author__ = "{p_planner.info.author}"\n'
        if p_planner.info.desc != "":
            output = f'"""\n{p_planner.info.desc}\n"""\n{output}'
            output = f'{output}__doc__ = "{p_planner.info.desc}"\n'
        return output

    @staticmethod
    def _get_init_pyi_str(
        plugin_dir: Path,
        shares: Iterable[AsyncShare | SyncShare],
        funcs: Iterable[Callable],
    ) -> str:
        refs: dict[str, list[str]] = {}
        varnames: list[str] = []
        autoget_varnames: list[str] = []

        for share in shares:
            if share.static:
                autoget_varnames.append(share.name)

            share_located = Path(share.__obj_file__)
            try:
                share_abs_located = share_located.resolve(strict=True)
            except Exception as e:
                raise PluginAutoGenError(
                    f"无法定位共享对象所在的模块位置，对应插件：{plugin_dir}"
                ) from e
            else:
                if plugin_dir.resolve(strict=True) not in share_abs_located.parents:
                    raise PluginAutoGenError(
                        f"共享对象 {share} 不在插件目录下定义，对应插件：{plugin_dir}"
                    )
                parts1 = share_abs_located.parts

            parts2 = plugin_dir.parts
            imp_parts = list(parts1[len(parts2) :])
            imp_parts[-1] = imp_parts[-1].rstrip(".py")

            mod = Importer.import_mod(share.__obj_module__, share_located.parent)
            for k in dir(mod):
                v = getattr(mod, k)
                if v is share:
                    share_varname = k
                    break
            else:
                raise PluginAutoGenError(
                    f"共享对象 {share} 在所属模块的全局作用域不存在引用，生成 .pyi 失败，"
                    f"对应插件：{plugin_dir}"
                )

            li = refs.setdefault(f".{'.'.join(imp_parts)}", [])
            if share.static:
                li.append(f"{share_varname} as _{share.name}")
            elif share_varname != share.name:
                li.append(f"{share_varname} as {share.name}")
            else:
                li.append(share_varname)
            varnames.append(share.name)

        for func in funcs:
            func_located = Path(getabsfile(func))
            try:
                func_abs_located = func_located.resolve(strict=True)
            except Exception as e:
                raise PluginAutoGenError(
                    f"无法定位导出函数所在模块的位置，对应插件：{plugin_dir}"
                ) from e
            else:
                if plugin_dir.resolve(strict=True) not in func_abs_located.parents:
                    raise PluginAutoGenError(
                        f"导出函数 {func} 不在插件目录下定义，对应插件：{plugin_dir}"
                    )
                parts1 = func_abs_located.parts

            parts2 = plugin_dir.parts
            imp_parts = list(parts1[len(parts2) :])
            imp_parts[-1] = imp_parts[-1].rstrip(".py")
            if func.__name__.startswith("_"):
                raise PluginAutoGenError(
                    f"导出函数 {func} 的名称不能以 _ 开头，对应插件：{plugin_dir}"
                )

            mod = Importer.import_mod(func.__module__, func_located.parent)
            for k in dir(mod):
                v = getattr(mod, k)
                if v is func:
                    break
            else:
                raise PluginAutoGenError(
                    f"导出函数 {func} 在所属模块的全局作用域不存在引用，生成 .pyi 失败，"
                    f"对应插件：{plugin_dir}"
                )
            refs.setdefault(f".{'.'.join(imp_parts)}", []).append(func.__name__)
            varnames.append(func.__name__)

        imp_lines = "\n".join(
            f"from {namespace} import {name}"
            for namespace, obj_names in refs.items()
            for name in obj_names
        )
        gets_str = "\n".join(f"{varname} = _{varname}.get()" for varname in autoget_varnames)
        vars_str = f"__all__ = {repr(tuple(varnames))}"

        if not len(varnames):
            return ""

        return "\n\n".join((imp_lines, gets_str, vars_str)) + "\n"

    @staticmethod
    def run_init(*plugin_dirs: str | PathLike[str], load_depth: int = 1) -> None:
        from ..bot.base import Bot

        tmp_bot = Bot()
        for p_dir in plugin_dirs:
            p_dir = Path(p_dir)
            if not p_dir.is_absolute():
                p_dir = Path.cwd().joinpath(p_dir)

            p_name = p_dir.parts[-1]
            p_conflicts = set(fname.split(".")[0] for fname in listdir(p_dir))
            pinit_path = p_dir.joinpath("__init__.py")
            pinit_typ_path = p_dir.joinpath("__init__.pyi")

            if p_name in sys.modules or p_name in sys.stdlib_module_names:
                raise PluginAutoGenError(
                    f"插件 {p_name} 与 python 内置模块或已加载模块重名，"
                    f"请修改名称（修改插件目录名）。对应插件：{p_dir}"
                )
            if not p_dir.joinpath("__plugin__.py").exists():
                raise PluginAutoGenError(
                    f"插件目录下不存在 __plugin__.py，无法解析。对应插件：{p_dir}"
                )
            if pinit_path.exists():
                remove(pinit_path)
            if pinit_typ_path.exists():
                remove(pinit_typ_path)

            with ExitStack() as ctx_stack:
                ctx_stack.enter_context(BotCtx().unfold(tmp_bot))

                prefix = ".".join(p_dir.parts[-load_depth:])
                p_entry_mod_name = f"{prefix}.__plugin__"
                p_entry_mod = Importer.import_mod(p_entry_mod_name, p_dir)
                for k in dir(p_entry_mod):
                    val = getattr(p_entry_mod, k)
                    if isinstance(val, PluginPlanner):
                        p_planner = val
                        p_shares = p_planner.shares
                        p_funcs = p_planner.funcs
                        break
                else:
                    raise PluginAutoGenError(
                        f"插件的 __plugin__.py 未实例化 {PluginPlanner.__name__} 类，"
                        f"无法解析。对应插件：{p_dir}"
                    )

                for share in p_shares:
                    if share.name in p_conflicts:
                        raise PluginAutoGenError(
                            f"插件的共享对象名 {share.name} 与插件根目录下的文件/目录名重复，"
                            "这将导致导入混淆，请修改共享对象名。"
                            f"对应插件：{p_dir}"
                        )
                for func in p_funcs:
                    if func.__name__ in p_conflicts:
                        raise PluginAutoGenError(
                            f"插件的导出函数名 {func.__name__} 与插件根目录下的文件/目录名重复，"
                            "这将导致导入混淆，请修改导出函数名"
                            f"对应插件：{p_dir}"
                        )

            try:
                pyi_content = PluginInitHelper._get_init_pyi_str(p_dir, p_shares, p_funcs)
                if pyi_content != "":
                    with open(pinit_typ_path, "w", encoding="utf-8") as fp:
                        fp.write(_AUTOGEN_COMMENT + pyi_content)
                with open(pinit_path, "w", encoding="utf-8") as fp:
                    fp.write(_AUTOGEN_COMMENT + PluginInitHelper._get_init_py_str(p_planner))

            except BaseException:
                if pinit_path.exists():
                    remove(pinit_path)
                if pinit_typ_path.exists():
                    remove(pinit_typ_path)
                raise

            Importer.clear_cache()


P_PLANNER_ATTR = "__plugin_planner__"
P_INFO_ATTR = "__plugin_info__"
_MODULE_SUFFIXES = ALL_EXTS


@singleton
class PluginLoader:
    def __init__(self) -> None:
        self._dir_caches: dict[str, Path] = {}

    def _build_plugin(
        self, p_name: str, entry: ModuleType | None, p_planner: PluginPlanner | None
    ) -> tuple[Plugin, bool]:
        if p_planner is None:

            if not hasattr(entry, P_PLANNER_ATTR):
                for k in dir(entry):
                    val = getattr(entry, k)
                    if isinstance(val, PluginPlanner):
                        setattr(entry, P_PLANNER_ATTR, val)
                        break

                else:
                    entry = cast(ModuleType, entry)
                    if entry.__file__ is None:
                        p_dir = Path(entry.__path__[0])
                    else:
                        p_dir = Path(entry.__file__).parent

                    raise PluginLoadError(
                        f"插件的 __plugin__.py 未实例化 {PluginPlanner.__name__} 类，无法加载。"
                        f"对应插件：{p_dir}"
                    )

            p_planner = getattr(entry, P_PLANNER_ATTR)

        p_planner = cast(PluginPlanner, p_planner)
        if p_planner._built:
            p = p_planner._plugin
            logger.debug(f"插件 {p.name} 已加载，重复加载将被跳过")
            return p, True

        p = p_planner.__p_build__(name=p_name)
        return p, False

    def load(
        self, plugin: ModuleType | str | PathLike[str] | PluginPlanner, load_depth: int
    ) -> tuple[Plugin, bool]:
        _plugin_repr = repr(plugin)

        if isinstance(plugin, PluginPlanner):
            p_name = f"_DynamicPlugin_0x{id(plugin):0x}"
            return self._build_plugin(p_name, entry=None, p_planner=plugin)

        if (
            isinstance(plugin, str)
            and not plugin.endswith(_MODULE_SUFFIXES)
            and not Path(plugin).exists()
        ):
            try:
                tmp_mod = Importer.import_mod(plugin)
                plugin = tmp_mod
            except DynamicImpSpecEmpty:
                pass

        if isinstance(plugin, ModuleType):
            if plugin.__file__ is None:
                p_dir = Path(plugin.__path__[0])
            else:
                p_dir = Path(plugin.__file__).parent
        else:
            p_dir = Path(plugin)
            if not p_dir.is_absolute():
                p_dir = Path.cwd().joinpath(p_dir).resolve()

        p_name = p_dir.parts[-1]
        logger.debug(f"尝试加载来自 {p_dir!r} 的插件：{p_name}")

        if p_name in sys.stdlib_module_names:
            raise PluginLoadError(
                f"尝试加载的插件 {p_name} 与 Python 内置模块重名，"
                f"请修改名称（修改插件目录名）。对应插件：{p_dir}"
            )
        if not p_dir.exists():
            raise PluginLoadError(f"插件目录不存在，无法加载。对应插件：{p_dir}")
        if not p_dir.joinpath("__plugin__.py").exists():
            raise PluginLoadError(f"插件目录下不存在 __plugin__.py，无法加载。对应插件：{p_dir}")

        p_mod = Importer.get_cache(p_dir)
        if p_mod is not None:
            p_entry_mod_name = f"{p_mod.__name__}.__plugin__"
        else:
            prefix = ".".join(p_dir.parts[-load_depth:])
            p_entry_mod_name = f"{prefix}.__plugin__"

        if p_name in self._dir_caches and p_dir.resolve() != self._dir_caches[p_name]:
            raise PluginLoadError(
                f"试图加载一个与已加载插件同名的插件，名称： {p_name}，"
                f"加载参数：{_plugin_repr}，尝试加载的插件：{p_dir}"
            )

        p_entry_mod = Importer.import_mod(p_entry_mod_name, p_dir)
        p, is_repeat = self._build_plugin(p_name, entry=p_entry_mod, p_planner=None)
        if not is_repeat:
            self._dir_caches[p.name] = p_dir.resolve()
            p_mod = cast(ModuleType, Importer.get_cache(p_dir))
            setattr(p_mod, P_INFO_ATTR, p.planner.info)
        return p, is_repeat
