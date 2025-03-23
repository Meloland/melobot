from __future__ import annotations

import logging
import sys
from os import PathLike
from pathlib import Path
from time import perf_counter
from types import ModuleType

from typing_extensions import Any, cast

from .._imp import ALL_EXTS, PKG_INIT_FILENAMES, ModuleLoader, SpecFinder
from ..ctx import BotCtx
from .base import GenericLogger, Logger, find_caller_stack

_SPEC_FINDER = SpecFinder()
_BOT_CTX = BotCtx()


class LogNode:
    def __init__(
        self,
        part: str,
        parent: LogNode | None = None,
    ) -> None:
        self.part = part
        self.logger: GenericLogger | None = None
        self.parent = parent
        self.children: dict[str, LogNode] = {}

    def resolve_logger(self) -> GenericLogger | None:
        if self.logger is not None:
            return self.logger
        if self.parent is not None:
            return self.parent.resolve_logger()
        return None

    def add_child(self, part: str) -> LogNode:
        if part not in self.children:
            self.children[part] = LogNode(part, self)
        return self.children[part]


class LogReflector:
    global_logger: GenericLogger | None = Logger("[global]")
    root_node = LogNode("")
    last_updated = perf_counter()

    @classmethod
    def set_global_logger(cls, logger: GenericLogger | None) -> None:
        cls.global_logger = logger

    @classmethod
    def set_module_logger(
        cls, module: str | PathLike[str] | ModuleType, logger: GenericLogger | None
    ) -> None:
        path = cls._get_mod_path(module)
        cur_node = cls.root_node
        for part in path.parts:
            cur_node = cur_node.add_child(part)
        cur_node.logger = logger
        cls.last_updated = perf_counter()

    @classmethod
    def _get_mod_path(cls, mod: str | PathLike[str] | ModuleType) -> Path:
        if isinstance(mod, str) and not mod.endswith(ALL_EXTS) and not Path(mod).exists():
            cached_mod = sys.modules.get(mod)
            if cached_mod is not None:
                return cls._get_module_path(cached_mod)

            spec = _SPEC_FINDER.find_spec(mod, paths=None)
            if spec is not None:
                loader = cast(ModuleLoader, spec.loader)
                path = loader.melobot_fp
                if path.parts[-1] in PKG_INIT_FILENAMES:
                    path = path.parent
                return path

        if isinstance(mod, ModuleType):
            path = cls._get_module_path(mod)
        else:
            path = Path(mod)
            if not path.is_absolute():
                try:
                    path = path.resolve(strict=True)
                except OSError:
                    raise FileNotFoundError(f"尝试解析模块路径时，发现路径 {path} 不存在")
        return path

    @staticmethod
    def _get_module_path(mod: ModuleType) -> Path:
        if mod.__file__ is None:
            # 此时对应没有 __init__.* 的包
            path = Path(mod.__path__[0])
        else:
            path = (
                Path(mod.__file__).parent
                if mod.__file__.endswith(PKG_INIT_FILENAMES)
                else Path(mod.__file__)
            )
        return path


def set_global_logger(logger: GenericLogger | None) -> None:
    LogReflector.set_global_logger(logger)


def set_module_logger(
    module: str | PathLike[str] | ModuleType, logger: GenericLogger | None
) -> None:
    LogReflector.set_module_logger(module, logger)


def reflect_logger(stack_depth: int = 3) -> GenericLogger:
    _, caller_path_str, *_ = find_caller_stack(stacklevel=stack_depth)
    try:
        caller_path = Path(caller_path_str).resolve(strict=True)
    except OSError as e:
        raise FileNotFoundError("自动决定日志器时，尝试解析调用模块的路径失败") from e

    cur_node = LogReflector.root_node
    for part in caller_path.parts:
        cur_node = cur_node.add_child(part)
    return GenericLogProxy(cur_node)


class GenericLogProxy(GenericLogger):
    def __init__(self, node: LogNode) -> None:
        self.__log_node__ = node
        self.__cache_ts__: float = 0
        self.__cache_logger__: GenericLogger | None = None

    @property
    def __logger__(self) -> GenericLogger | None:
        return self.__get_logger__()

    def __get_logger__(self) -> GenericLogger | None:
        if LogReflector.last_updated > self.__cache_ts__:
            logger = self.__log_node__.resolve_logger()
            self.__cache_ts__ = perf_counter()
            self.__cache_logger__ = logger
        else:
            logger = self.__cache_logger__

        if logger is None:
            if bot := _BOT_CTX.try_get():
                logger = bot.logger
            if logger is None:
                logger = LogReflector.global_logger
        return logger

    def __log_meth__(self, meth_name: str, *_: Any, **kwargs: Any) -> None:
        logger = self.__logger__
        if logger is not None:
            if isinstance(logger, logging.Logger):
                kwargs["stacklevel"] = 3
            getattr(logger, meth_name)(*_, **kwargs)

    def debug(self, *_: Any, **__: Any) -> None:
        self.__log_meth__("debug", *_, **__)

    def info(self, *_: Any, **__: Any) -> None:
        self.__log_meth__("info", *_, **__)

    def warning(self, *_: Any, **__: Any) -> None:
        self.__log_meth__("warning", *_, **__)

    def error(self, *_: Any, **__: Any) -> None:
        self.__log_meth__("error", *_, **__)

    def critical(self, *_: Any, **__: Any) -> None:
        self.__log_meth__("critical", *_, **__)

    def exception(self, *_: Any, **__: Any) -> None:
        self.__log_meth__("exception", *_, **__)

    def generic_lazy(self, *_: Any, **__: Any) -> None:
        self.__log_meth__("generic_lazy", *_, **__)

    def generic_obj(self, *_: Any, **__: Any) -> None:
        self.__log_meth__("generic_obj", *_, **__)


def __getattr__(name: str) -> Any:
    if name != "logger":
        raise AttributeError
    return reflect_logger()


logger: GenericLogger
