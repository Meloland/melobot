import concurrent.futures
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from argparse import Namespace
from pathlib import Path

from typing_extensions import Callable

from melobot import __version__
from melobot._run import CLI_LAST_EXIT_CODE, CLI_RUN_ALIVE_FLAG, CLI_RUN_FLAG
from melobot.typ import ExitCode

from ._signal import ShutdownState, clear_alive_sig, shutdown_signals
from .version import PROG_NAME


def main(args: Namespace) -> None:
    Observer, Handler = get_requires()
    observer = Observer()
    reload_signal = threading.Event()
    for path in args.watch:
        observer.schedule(Handler(path, reload_signal), path, recursive=True)

    if not args.entry_file.endswith(".py"):
        entry_str = f"{args.entry_file}.py"
    else:
        entry_str = args.entry_file

    entry_path = Path(entry_str)
    try:
        entry = entry_path.resolve(strict=True).as_posix()
    except FileNotFoundError:
        raise FileNotFoundError(f"不存在的入口文件：{args.entry_file}")

    cmd = [sys.executable, entry, *args.bot_args]
    cwd = Path.cwd().resolve().as_posix()
    os.environ[CLI_RUN_FLAG] = "1"
    tmp_dir = Path(tempfile.mkdtemp()).resolve()
    os.environ[CLI_RUN_ALIVE_FLAG] = str(
        tmp_dir.joinpath(f"melobot_cli_dev_run_{threading.get_native_id()}.signal")
    )

    state = ShutdownState()
    observer_started = False
    with shutdown_signals(state):
        try:
            if not state.requested:
                observer.start()
                observer_started = True
            while not state.requested:
                reload_signal.clear()
                create_alive_sig()
                if state.requested:
                    break

                with subprocess.Popen(
                    cmd,
                    env=os.environ,
                    cwd=cwd,
                    stdin=sys.stdin,
                    stdout=sys.stdout,
                    stderr=sys.stderr,
                ) as proc:
                    try:
                        if state.requested:
                            clear_alive_sig()
                        retcode = _wait_for_exit(proc, reload_signal, state)
                    finally:
                        clear_alive_sig()

                os.environ.pop(CLI_LAST_EXIT_CODE, None)

                if state.requested or retcode == ExitCode.NORMAL.value:
                    break

                if retcode == ExitCode.RESTART.value:
                    print(f"\n[{PROG_NAME}] 正在重启 Bot 主程序\n")
                    os.environ[CLI_LAST_EXIT_CODE] = str(ExitCode.RESTART.value)
                    continue

                if retcode == ExitCode.ERROR.value:
                    break

                print()
                print(f"[{PROG_NAME}] Bot 主程序返回了意料之外的退出码: {retcode}")
                print(f"[{PROG_NAME}] 若提示“已安全停止运行”，则无需关注此警告")
                break

        finally:
            try:
                clear_alive_sig()
            finally:
                try:
                    observer.stop()
                finally:
                    try:
                        if observer_started:
                            observer.join()
                    finally:
                        shutil.rmtree(tmp_dir)


def _wait_for_exit(
    proc: subprocess.Popen, reload_signal: threading.Event, state: ShutdownState
) -> int:
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        process_exit = executor.submit(proc.wait)
        try:
            reload_requested = executor.submit(reload_signal.wait)
            futures: list[concurrent.futures.Future] = [process_exit, reload_requested]
            concurrent.futures.wait(futures, return_when=concurrent.futures.FIRST_COMPLETED)
            should_reload = reload_signal.is_set()
            if should_reload or state.requested:
                clear_alive_sig()
            retcode = process_exit.result()
            if should_reload and not state.requested:
                return ExitCode.RESTART.value
            return retcode
        finally:
            try:
                clear_alive_sig()
            finally:
                # 所有退出路径都唤醒监测线程，避免线程池关闭时永久等待。
                reload_signal.set()


def create_alive_sig() -> None:
    with open(os.environ[CLI_RUN_ALIVE_FLAG], "wb"):
        pass


def get_requires() -> tuple[Callable, Callable]:
    try:
        from watchdog.events import FileSystemEvent, FileSystemEventHandler
        from watchdog.observers import Observer

        class Handler(FileSystemEventHandler):
            def __init__(self, path: str, reload_signal: threading.Event) -> None:
                super().__init__()
                self.path = Path(path).resolve()
                self.re_signal = reload_signal

            def _on_event(self, event: FileSystemEvent) -> None:
                e_path = Path(str(event.src_path)).resolve()

                if "__pycache__" in e_path.parts or os.environ[CLI_RUN_ALIVE_FLAG] in e_path.parts:
                    return

                self.re_signal.set()

            def on_moved(self, event: FileSystemEvent) -> None:
                self._on_event(event)

            def on_created(self, event: FileSystemEvent) -> None:
                self._on_event(event)

            def on_modified(self, event: FileSystemEvent) -> None:
                self._on_event(event)

            def on_deleted(self, event: FileSystemEvent) -> None:
                self._on_event(event)

        return Observer, Handler

    except ModuleNotFoundError:
        print(
            f"部分功能需要额外的依赖。安装这些额外依赖：pip install 'melobot[cli]>={__version__}'",
            file=sys.stderr,
        )
        sys.exit(1)
