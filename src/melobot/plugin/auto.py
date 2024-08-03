import importlib.util
import sys
from inspect import getabsfile
from os import PathLike, remove
from pathlib import Path

from ..exceptions import BotPluginError
from ..plugin.ipc import AsyncShare, SyncShare
from ..typing import TYPE_CHECKING, Any, Callable, Iterable, ModuleType
from .base import PluginMetaData

if TYPE_CHECKING:
    from ..bot.base import Bot

with open(Path(__file__).parent.joinpath("__init__.template.py"), encoding="utf-8") as fp:
    _BASE_INIT_PY_STR = fp.read()


def imp_from_path(name: str, path: str | PathLike[str]) -> ModuleType:
    if name in sys.modules:
        return sys.modules[name]

    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    sys.modules[name] = mod
    return mod


def _get_init_py_str(plugin_name: str) -> str:
    return _BASE_INIT_PY_STR.replace("__PLUGIN_NAME__", plugin_name)


def _get_init_pyi_str(
    plugin_dir: Path, shares: Iterable[AsyncShare | SyncShare], funcs: Iterable[Callable]
):
    refs: dict[str, list[str]] = {}
    varnames: list[str] = []
    need_get_varnames: list[str] = []
    p_dirname = plugin_dir.parts[-1]

    for share in shares:
        if share._static:
            need_get_varnames.append(share.name)

        share_located = Path(share.__obj_file__)
        parts1 = share_located.resolve(strict=True).parts
        parts2 = plugin_dir.parts
        imp_parts = list(parts1[len(parts2) :])
        imp_parts[-1] = imp_parts[-1].rstrip(".py")

        mod = imp_from_path(share.__obj_module__, share_located)
        for k in dir(mod):
            v = getattr(mod, k)
            if v is share:
                share_varname = k
                break
        else:
            raise BotPluginError(
                f"{share} 在所属模块的全局作用域不存在引用，生成 .pyi 失败"
            )
        refs.setdefault(f".{'.'.join(imp_parts)}", []).append(
            share.name if not share._static else f"{share_varname} as _{share.name}"
        )
        varnames.append(share.name)

    for func in funcs:
        func_located = Path(getabsfile(func))
        parts1 = func_located.resolve(strict=True).parts
        parts2 = plugin_dir.parts
        imp_parts = list(parts1[len(parts2) :])
        imp_parts[-1] = imp_parts[-1].rstrip(".py")

        mod = imp_from_path(f"{p_dirname}.{'.'.join(imp_parts)}", func_located)
        refs.setdefault(f".{'.'.join(imp_parts)}", []).append(func.__name__)
        varnames.append(func.__name__)

    imp_lines = "\n".join(
        f"from {namespace} import {name}"
        for namespace, obj_names in refs.items()
        for name in obj_names
    )
    gets_str = "\n".join(f"{varname} = _{varname}.get()" for varname in need_get_varnames)
    vars_str = "__all__ = (" + ", ".join(repr(name) for name in varnames) + ")"
    return "\n\n".join((imp_lines, gets_str, vars_str)) + "\n"


def run_plugin_init(plugin_dir: str | PathLike[str]) -> None:
    p_dir = Path(plugin_dir)
    p_dirname = p_dir.parts[-1]
    pinit_path = p_dir.joinpath("__init__.py")
    pinit_typ_path = p_dir.joinpath("__init__.pyi")

    if p_dirname in sys.modules.keys():
        print(f"尝试初始化的插件的目录名 {p_dirname} 与内置模块重名，请修改")
    if not p_dir.is_absolute():
        raise BotPluginError("插件初始化时，需要提供插件目录的绝对路径")
    if not p_dir.joinpath("__plugin__.py").exists():
        raise BotPluginError("插件目录下不存在 __plugin__.py，无法运行初始化")
    if pinit_path.exists():
        remove(pinit_path)
    if pinit_typ_path.exists():
        remove(pinit_typ_path)

    p_load_mod = imp_from_path(f"{p_dirname}.__plugin__", p_dir / "__plugin__.py")
    for k in dir(p_load_mod):
        v = getattr(p_load_mod, k)
        if isinstance(v, PluginMetaData):
            p_name = v.name
            p_shares = v.shares
            p_funcs = v.funcs
            break
    else:
        raise BotPluginError("插件的 __plugin__.py 未实例化元数据类")

    with open(pinit_typ_path, "w", encoding="utf-8") as fp:
        fp.write(_get_init_pyi_str(p_dir, p_shares, p_funcs))
    with open(pinit_path, "w", encoding="utf-8") as fp:
        fp.write(_get_init_py_str(p_name))

    del_mod_names: list[str] = []
    for mod_name in sys.modules.keys():
        if mod_name == p_dirname or mod_name.startswith(f"{p_dirname}."):
            del_mod_names.append(mod_name)
    for mod_name in del_mod_names:
        sys.modules.pop(mod_name)


def get_plugin_attr(bot: "Bot", plugin_name: str, name: str) -> Any:
    obj = bot.ipc_manager.get(plugin_name, name)
    if obj._static:
        return obj.get()
    else:
        return obj
