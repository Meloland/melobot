"""
此模块提供在 melobot 用例中对多进程的支持。
主要实现 spawn 模式子进程的自定义入口，以及避免默认序列化方式导致的级联加载。
基于对 spawn 模式子进程入口点的劫持，以及构建自定义可序列化对象。
只要不使用本模块的进程创建接口，就自动回退到 multiprocessing 原始逻辑
"""

# TODO: 由于存在侵入性设计，因此每个 py minor 版本都应该测试验证
import multiprocessing.spawn as spawn_mod
import multiprocessing.util as util_mod
import sys
from functools import wraps
from multiprocessing import current_process

from typing_extensions import Any

from ._imp import ALL_EXTS
from ._meta import MetaInfo

_PNAME_PREFIX = "MeloBot_MP"
MP_MODULE_NAME = "__mp_main__"
ROOT_MODULE_DIR = MetaInfo.pkg_path.parent.as_posix()


def in_main_process() -> bool:
    """判断当前进程是否为主进程"""
    return current_process().name == "MainProcess"


def _wrapped_get_preparation_data(name: str) -> dict:
    data = _original_get_preparation_data(name)
    if SpawnProcess.owned(name):
        data["sys_path"].insert(0, _P_STATUS[name]["dir"])
        data["sys_argv"] = _P_STATUS[name]["argv"]
        data["dir"] = data["orig_dir"] = _P_STATUS[name]["dir"]

        sentinel = object()
        mod_name = data.get("init_main_from_name", sentinel)
        if mod_name is not sentinel and mod_name not in ("__main__", MP_MODULE_NAME):
            raise RuntimeError(
                f"子进程中 __main__ 模块从名称 {mod_name!r} 加载，这种情况下无法安全生成子进程"
            )
        data.pop("init_main_from_name", None)
        data["init_main_from_path"] = _P_STATUS[name]["entry"]
    return data


def _wrapped_get_command_line(**kwargs: Any) -> Any:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--multiprocessing-fork"] + [
            "%s=%r" % item for item in kwargs.items()
        ]
    else:
        prog = (
            f"import sys; sys.path.insert(0, {ROOT_MODULE_DIR!r}); import melobot.mp; "
            "from multiprocessing.spawn import spawn_main; spawn_main(%s)"
        )
        prog %= ", ".join("%s=%r" % item for item in kwargs.items())
        opts = util_mod._args_from_interpreter_flags()  # type: ignore[attr-defined]
        return [spawn_mod.get_executable()] + opts + ["-c", prog, "--multiprocessing-fork"]


def _wrapped_prepare(data: Any) -> None:
    ret = _original_prepare(data)
    if SpawnProcess.owned(data["name"]):
        import signal

        # 默认重置常见的信号处理，子进程由父进程全权管理
        signals_to_ignore: list[signal.Signals] = [signal.SIGINT, signal.SIGTERM]
        if sys.platform == "win32":
            signals_to_ignore.append(signal.SIGBREAK)
        for sig in signals_to_ignore:
            signal.signal(sig, signal.SIG_IGN)
    return ret


_original_get_preparation_data = spawn_mod.get_preparation_data
spawn_mod.get_preparation_data = wraps(_original_get_preparation_data)(
    _wrapped_get_preparation_data
)

_original_get_command_line = spawn_mod.get_command_line
spawn_mod.get_command_line = wraps(_original_get_command_line)(_wrapped_get_command_line)

_original_prepare = spawn_mod.prepare
spawn_mod.prepare = wraps(_original_prepare)(_wrapped_prepare)


import pickle
from concurrent.futures import ProcessPoolExecutor as _ProcessPoolExecutor
from functools import partial
from multiprocessing import get_context
from multiprocessing.context import SpawnContext as _SpawnContext
from multiprocessing.pool import Pool
from os import PathLike
from os.path import normpath
from pathlib import Path
from threading import RLock
from types import FunctionType, MethodType, ModuleType

from typing_extensions import Callable, Iterable, Mapping, TypeAlias, TypedDict, cast


class _ProcessStatus(TypedDict):
    name: str
    entry: str
    argv: list[str]
    dir: str


_P_STATUS: dict[str, _ProcessStatus] = {}


class SpawnProcess(get_context("spawn").Process):  # type: ignore[name-defined,misc]
    """melobot 进程类（使用 spawn 模式生成子进程）"""

    def __init__(
        self,
        entry: str | PathLike[str] | Path,
        argv: list[str] | None = None,
        target: Callable[..., object] | None = None,
        name: str | None = None,
        args: Iterable[Any] | None = None,
        kwargs: Mapping[str, Any] | None = None,
        *,
        daemon: bool | None = None,
    ) -> None:
        """初始化一个子进程对象

        :param entry: 子进程的入口模块（必须是文件）
        :param argv: 子进程的 `argv`，为空时使用默认设置
        :param target: 子进程的目标函数
        :param name: 子进程的标识名称，注意真实的进程名称与此参数不相等，只是包含
        :param args: 目标函数的参数
        :param kwargs: 目标函数的参数
        :param daemon: 是否是守护进程
        """
        if not in_main_process():
            raise RuntimeError(
                "不应该在 melobot 管理的子进程中继续创建子进程。"
                "出现此异常可能是因为初始化参数“入口路径”设置错误，导致创建进程的代码在子进程中再次执行"
            )

        super().__init__(
            None,
            target,
            name,
            () if args is None else args,
            {} if kwargs is None else kwargs,
            daemon=daemon,
        )
        order = self.name.split("-")[-1]
        self.init_name = name
        # 重设 name 属性，用于后续在 hack 中区分进程
        self.main_part = f"{id(self):x}" if self.init_name is None else self.init_name
        self.name: str = f"{_PNAME_PREFIX}_{self.main_part}-{order}"

        try:
            entry_file = Path(entry).resolve(True)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"子进程 {self.main_part} 的入口不存在: {entry!r}") from e

        if not entry_file.is_file() or not entry_file.as_posix().endswith(ALL_EXTS):
            raise ValueError(f"子进程 {self.main_part} 的入口不是可加载的文件: {entry_file!r}")

        # 再使用一次 normpath，保证与原始实现一样的兼容性
        entry_norm_path = normpath(str(entry_file))
        _P_STATUS[self.name] = {
            "name": self.name,
            "entry": entry_norm_path,
            "argv": argv if argv is not None else [entry_norm_path],
            "dir": normpath(str(entry_file.parent)),
        }

    @staticmethod
    def owned(name: str) -> bool:
        return "melobot" in name.lower()


def in_melobot_sub_process() -> bool:
    """判断当前进程是否为 melobot 管理的子进程"""
    return SpawnProcess.owned(current_process().name)


class _BanOriginalProcess:
    def __get__(self, *_: Any, **__: Any) -> None:
        raise AttributeError(f"内部尝试引用原始 Process 对象，请报告关于 {__name__} 模块的 bug")


class SpawnContext(_SpawnContext):
    Process = cast(Any, _BanOriginalProcess())

    def __init__(self, entry: str | PathLike[str] | Path, argv: list[str] | None = None) -> None:
        super().__init__()
        self.process_entry = entry
        self.process_argv = argv

    def __getattr__(self, name: str) -> Any:
        if name == "Process":
            return partial(SpawnProcess, self.process_entry, self.process_argv)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")


class SpawnProcessPool(Pool):
    """melobot 进程池类（使用 spawn 模式生成子进程）"""

    def __init__(
        self,
        entry: str | PathLike[str] | Path,
        argv: list[str] | None = None,
        processes: int | None = None,
        initializer: Callable[..., object] | None = None,
        initargs: Iterable[Any] | None = None,
        maxtasksperchild: int | None = None,
    ) -> None:
        """初始化一个进程池对象

        :param entry: 所有子进程的入口模块（必须是文件）
        :param argv: 所有子进程的 `argv`，为空时使用默认设置
        :param processes: 进程数
        :param initializer: 初始化函数
        :param initargs: 初始化函数的参数
        :param maxtasksperchild: 每个子进程执行的任务数，达到此数时销毁并生成新进程
        """
        if initargs is None:
            init_args = ()
        super().__init__(
            processes, initializer, init_args, maxtasksperchild, SpawnContext(entry, argv)
        )


class SpawnProcessPoolExecutor(_ProcessPoolExecutor):
    """melobot 进程池执行器类（使用 spawn 模式生成子进程）"""

    def __init__(
        self,
        entry: str | PathLike[str] | Path,
        argv: list[str] | None = None,
        max_workers: int | None = None,
        initializer: Callable[..., object] | None = None,
        initargs: Iterable[Any] | None = None,
    ) -> None:
        """初始化一个进程池执行器对象

        :param entry: 所有子进程的入口模块（必须是文件）
        :param argv: 所有子进程的 `argv`，为空时使用默认设置
        :param max_workers: worker（进程）的数量
        :param initializer: 初始化函数
        :param initargs: 初始化函数的参数
        """
        if initargs is None:
            init_args = ()
        super().__init__(max_workers, SpawnContext(entry, argv), initializer, init_args)


Process: TypeAlias = SpawnProcess
Context: TypeAlias = SpawnContext
ProcessPool: TypeAlias = SpawnProcessPool
ProcessPoolExecutor: TypeAlias = SpawnProcessPoolExecutor


_EMPTY = object()
_DUMMY_CLS = type("_DUMMY_CLS", (), {})
# 注意这个递归锁在序列化和反序列化时，不是同一个（在不同进程中）
_PICKLE_RLOCK = RLock()


class PBox:
    def __init__(
        self,
        value: Any = _EMPTY,
        name: str | None = None,
        module: str | None = None,
        entry: str | PathLike[str] | Path | None = None,
    ) -> None:
        """pickle 包装器

        更改或指定需要 pickle 的对象的来源

        :param value: 和 `name` 二选一，指定需要 pickle 的对象，默认值为一个哨兵对象（表示无值）
        :param name: 和 `value` 二选一，指定需要 pickle 的对象的名称
        :param module: pickle 的对象的来源模块名，为空时映射到进程的入口模块
        :param entry: pickle 的对象的来源模块的路径，如果为空则只依赖于模块名进行加载
        """
        if value is _EMPTY and name is None:
            raise ValueError("值参数和名称参数不能同时为空")
        if value is not _EMPTY and name is not None:
            raise ValueError("值参数和名称参数不能同时存在")
        if isinstance(value, MethodType):
            raise ValueError("类或实例的方法不支持 pickle，请尝试 pickle 整个类或实例而不是方法")

        # 序列化后的 bytes
        self.value: bytes
        # 是否有值，如果无值则反序列化时不使用 value 属性，而是直接从模块中提取
        self.has_value: bool
        # 反序列化前，预先加载的模块名
        self.module = cast(str, MP_MODULE_NAME if module in ("", None) else module)

        # 反序列化时，预先加载的模块的文件路径，为空时只依赖模块名加载模块
        self.entry: str | None
        if entry is not None:
            try:
                abs_entry_path = Path(entry).resolve(True)
            except FileNotFoundError as e:
                raise FileNotFoundError(f"入口路径 {entry!r} 不存在") from e
            self.entry = abs_entry_path.as_posix()

            if self.module != MP_MODULE_NAME:
                mod_parts = tuple(self.module.split("."))
                if "" in mod_parts:
                    raise ValueError(f"模块名 {module!r} 有误或存在相对导入语义")

                path_parts = abs_entry_path.parts[:-1] + (abs_entry_path.stem,)
                if path_parts[-len(mod_parts) :] != mod_parts:
                    raise ValueError(
                        "模块名 split('.') 后的序列，不是路径绝对化并去除扩展名后 split('/') 得到序列的尾子序列"
                    )
        else:
            self.entry = None

        # 这些属性在序列化时会被排除在外
        self._serial_args = (value, name)
        self._orig_value = value

    def _serialize(self, value: Any, name: str | None) -> None:
        if value is _EMPTY:
            self.has_value = False
            name = cast(str, name)
            self.value = name.encode("utf-8")
            return

        with _PICKLE_RLOCK:
            self.has_value = True
            name_owner: FunctionType | type
            if getattr(value, "__qualname__", None) not in (None, ""):
                qname = value.__qualname__
                name_owner = value
                real_mod = getattr(value, "__module__", None)
                if real_mod in (None, ""):
                    raise ValueError(f"对象 {value} 所属模块无法找到，因此不能被 pickle")
            else:
                cls = getattr(value, "__class__", _EMPTY)
                if cls is _EMPTY:
                    raise ValueError(f"对象 {value} 的类无法找到，因此不能被 pickle")

                _qname = cast(str | None, getattr(cls, "__qualname__", None))
                if _qname in (None, ""):
                    raise ValueError(f"对象 {value} 的类没有有效的名称，因此不能被 pickle")
                qname = cast(str, _qname)
                name_owner = cast(type, cls)

                real_mod = getattr(cls, "__module__", None)
                if real_mod in (None, ""):
                    raise ValueError(f"对象 {value} 的类所属模块无法找到，因此不能被 pickle")

            real_mod = cast(str | None, real_mod)
            real_name = getattr(name_owner, "__name__", _EMPTY)
            real_qname = getattr(name_owner, "__qualname__", _EMPTY)

            # 获取 pickle 要验证的模块，如果存在则暂时保存
            mod = sys.modules.get(self.module)
            orig_mod = mod if mod is not None else None
            fake_mod = ModuleType(self.module)

            # 逐级生成属性，直到最后一层
            parts = qname.split(".")
            idx = 0
            node = fake_mod
            while idx < len(parts) - 1:
                setattr(node, parts[idx], _DUMMY_CLS())
                node = getattr(node, parts[idx])
                idx += 1
            # 最后一层填充实际值
            setattr(node, parts[-1], name_owner)

            # 对于实际的对象，构建临时环境来欺骗 pickle
            sys_modified = False
            try:
                name_owner.__qualname__ = qname
                name_owner.__name__ = qname.split(".")[-1]
                name_owner.__module__ = self.module
                sys.modules[self.module] = fake_mod
                sys_modified = True
                self.value = pickle.dumps(value)
            finally:
                if sys_modified:
                    if orig_mod is None:
                        del sys.modules[self.module]
                    else:
                        sys.modules[self.module] = orig_mod

                if real_mod is None:
                    if hasattr(name_owner, "__module__"):
                        del name_owner.__module__
                else:
                    name_owner.__module__ = real_mod

                if real_name is _EMPTY:
                    if hasattr(name_owner, "__name__"):
                        del name_owner.__name__
                else:
                    name_owner.__name__ = cast(str, real_name)

                if real_qname is _EMPTY:
                    if hasattr(name_owner, "__qualname__"):
                        del name_owner.__qualname__
                else:
                    name_owner.__qualname__ = cast(str, real_qname)

    def __reduce__(self) -> tuple[Callable, tuple[Any, ...]]:
        try:
            self._serialize(*self._serial_args)
        except Exception as e:
            if self._orig_value is _EMPTY:
                raise pickle.PicklingError(f"Pickle 失败，{e}") from e
            else:
                raise pickle.PicklingError(f"Pickle 对象 {self._orig_value} 失败，{e}") from e
        else:
            return (_deserialize, (self.value, self.has_value, self.module, self.entry))


def _deserialize(value: bytes, has_value: bool, module: str, entry: str | None) -> Any:
    from ._imp import Importer

    with _PICKLE_RLOCK:
        try:
            dir_path = (
                Path(entry).resolve(strict=True).parent.as_posix() if entry is not None else None
            )
            mod = Importer.import_mod(module, dir_path)
            if has_value:
                return pickle.loads(value)
            else:
                return getattr(mod, value.decode("utf-8"))
        except Exception as e:
            raise pickle.UnpicklingError(f"Unpickle 失败，{e}") from e
