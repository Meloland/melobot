import re
import sys
from contextlib import ExitStack
from inspect import getabsfile
from os import PathLike, listdir, remove
from pathlib import Path
from time import time
from types import ModuleType
from typing import Any, Callable, Iterable

from ..ctx import BotCtx, LoggerCtx
from ..exceptions import PluginError
from ..utils import singleton
from .base import Plugin
from .imp import Importer
from .ipc import AsyncShare, SyncShare


def plugin_get_attr(p_name: str, name: str) -> Any:
    obj = BotCtx().get().ipc_manager.get(p_name, name)
    if obj.static:
        return obj.get()
    return obj


class PluginInitHelper:
    with open(
        Path(__file__).parent.joinpath("__init__.template.py"), encoding="utf-8"
    ) as fp:
        _BASE_INIT_PY_STR = fp.read()

    @staticmethod
    def _get_init_py_str() -> str:
        return re.sub(
            r"_VAR(\d+)",
            lambda match: f"_{int(time()):#x}{match.group(1)}",
            PluginInitHelper._BASE_INIT_PY_STR,
        )

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
            parts1 = share_located.resolve(strict=True).parts
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
                raise PluginError(
                    f"共享对象 {share} 在所属模块的全局作用域不存在引用，生成 .pyi 失败"
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
            parts1 = func_located.resolve(strict=True).parts
            parts2 = plugin_dir.parts
            imp_parts = list(parts1[len(parts2) :])
            imp_parts[-1] = imp_parts[-1].rstrip(".py")
            if func.__name__.startswith("_"):
                raise PluginError(f"导出函数 {func} 的名称不能以 _ 开头")

            mod = Importer.import_mod(func.__module__, func_located.parent)
            for k in dir(mod):
                v = getattr(mod, k)
                if v is func:
                    break
            else:
                raise PluginError(
                    f"导出函数 {func} 在所属模块的全局作用域不存在引用，生成 .pyi 失败"
                )
            refs.setdefault(f".{'.'.join(imp_parts)}", []).append(func.__name__)
            varnames.append(func.__name__)

        imp_lines = "\n".join(
            f"from {namespace} import {name}"
            for namespace, obj_names in refs.items()
            for name in obj_names
        )
        gets_str = "\n".join(
            f"{varname} = _{varname}.get()" for varname in autoget_varnames
        )
        vars_str = f"__all__ = {repr(tuple(varnames))}"

        if not len(varnames):
            return ""

        return "\n\n".join((imp_lines, gets_str, vars_str)) + "\n"

    @staticmethod
    def run_init(*plugin_dirs: str | PathLike[str], load_depth: int = 1) -> None:
        # pylint: disable=cyclic-import
        from melobot.bot import Bot

        tmp_bot = Bot(enable_log=False)

        for p_dir in plugin_dirs:
            p_dir = Path(p_dir)
            if not p_dir.is_absolute():
                p_dir = Path.cwd().joinpath(p_dir)

            p_name = p_dir.parts[-1]
            p_conflicts = set(fname.split(".")[0] for fname in listdir(p_dir))
            pinit_path = p_dir.joinpath("__init__.py")
            pinit_typ_path = p_dir.joinpath("__init__.pyi")

            if p_name in sys.modules or p_name in sys.stdlib_module_names:
                raise PluginError(
                    f"尝试初始化的插件 {p_name} 与 python 内置模块或已加载模块重名，请修改名称（修改插件目录名）"
                )
            if not p_dir.joinpath("__plugin__.py").exists():
                raise PluginError("插件目录下不存在 __plugin__.py，无法运行初始化")
            if pinit_path.exists():
                remove(pinit_path)
            if pinit_typ_path.exists():
                remove(pinit_typ_path)

            with ExitStack() as ctx_stack:
                ctx_stack.enter_context(BotCtx().in_ctx(tmp_bot))
                ctx_stack.enter_context(LoggerCtx().in_ctx(tmp_bot.logger))

                prefix = ".".join(p_dir.parts[-load_depth:])
                p_load_mod_name = f"{prefix}.__plugin__"
                p_load_mod = Importer.import_mod(p_load_mod_name, p_dir)
                for k in dir(p_load_mod):
                    v = getattr(p_load_mod, k)
                    if isinstance(v, type) and v is not Plugin and issubclass(v, Plugin):
                        p = v()
                        p_shares = p.shares
                        p_funcs = p.funcs
                        break
                else:
                    raise PluginError(
                        "插件的 __plugin__.py 未实例化 Plugin 类，无法运行初始化"
                    )
                for share in p_shares:
                    if share.name in p_conflicts:
                        raise PluginError(
                            f"插件的共享对象名 {share.name} 与插件根目录下的文件/目录名重复，"
                            "这将导致导入混淆，请修改共享对象名"
                        )
                for func in p_funcs:
                    if func.__name__ in p_conflicts:
                        raise PluginError(
                            f"插件的导出函数名 {func.__name__} 与插件根目录下的文件/目录名重复，"
                            "这将导致导入混淆，请修改导出函数名"
                        )

            try:
                pyi_content = PluginInitHelper._get_init_pyi_str(p_dir, p_shares, p_funcs)
                if pyi_content != "":
                    with open(pinit_typ_path, "w", encoding="utf-8") as fp:
                        fp.write(pyi_content)
                    with open(pinit_path, "w", encoding="utf-8") as fp:
                        fp.write(PluginInitHelper._get_init_py_str())

            except Exception:
                if pinit_path.exists():
                    remove(pinit_path)
                if pinit_typ_path.exists():
                    remove(pinit_typ_path)
                raise

            Importer.clear_cache()


@singleton
class PluginLoader:
    def _build_plugin(self, p_name: str, p_load_mod: ModuleType) -> Plugin:
        for k in dir(p_load_mod):
            v = getattr(p_load_mod, k)
            if isinstance(v, type) and v is not Plugin and issubclass(v, Plugin):
                p: Plugin = v()
                break
        else:
            raise PluginError("插件的 __plugin__.py 未实例化 Plugin 类，无法加载")

        p.__plugin_build__(p_name)
        return p

    def load(
        self, plugin: ModuleType | str | PathLike[str] | Plugin, load_depth: int
    ) -> Plugin:
        logger = LoggerCtx().get()

        if isinstance(plugin, Plugin):
            plugin.__plugin_build__(f"DynamicPlugin_0x{id(plugin):0x}")
            return plugin

        if isinstance(plugin, ModuleType):
            if plugin.__file__ is None:
                p_dir = Path(plugin.__path__[0])
            else:
                p_dir = Path(plugin.__file__).parent
        else:
            p_dir = Path(plugin)
            if not p_dir.is_absolute():
                p_dir = Path.cwd().joinpath(p_dir).resolve(strict=True)

        logger.debug(f"尝试加载来自 {repr(p_dir)} 的插件")

        p_name = p_dir.parts[-1]
        if p_name in sys.stdlib_module_names:
            raise PluginError(
                f"尝试加载的插件 {p_name} 与 Python 内置模块重名，请修改名称（修改插件目录名）"
            )
        if not p_dir.joinpath("__plugin__.py").exists():
            raise PluginError("插件目录下不存在 __plugin__.py，无法加载")

        p_mod_cache = Importer.get_cache(p_dir)
        if p_mod_cache is not None:
            p_load_mod_name = f"{p_mod_cache.__name__}.__plugin__"
        else:
            prefix = ".".join(p_dir.parts[-load_depth:])
            p_load_mod_name = f"{prefix}.__plugin__"

        p_load_mod = Importer.import_mod(p_load_mod_name, p_dir)
        _plugin = self._build_plugin(p_name, p_load_mod)
        return _plugin
