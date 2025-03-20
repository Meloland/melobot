import concurrent.futures
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from argparse import Namespace
from pathlib import Path

from typing_extensions import Any, Callable

from melobot import __version__
from melobot._run import CLI_LAST_EXIT_CODE, CLI_RUN_ALIVE_FLAG, CLI_RUN_FLAG, ExitCode


def main(args: Namespace) -> None:
    Observer, Handler = get_requires()
    observer = Observer()
    reload_signal = threading.Event()
    for path in args.watch:
        observer.schedule(Handler(path, reload_signal), path, recursive=True)

    entry_path = Path(args.entry_file)
    if not entry_path.is_absolute():
        entry = str(entry_path.resolve())
    else:
        entry = str(entry_path)

    if not entry.endswith(".py"):
        entry += ".py"
    if not Path(entry).exists():
        print(f"不存在的入口文件：{str(entry)}")
        sys.exit(1)

    cmd = [sys.executable, entry]
    cwd = str(Path.cwd().resolve())
    os.environ[CLI_RUN_FLAG] = "1"
    tmp_dir = Path(tempfile.mkdtemp()).resolve()
    os.environ[CLI_RUN_ALIVE_FLAG] = str(
        tmp_dir.joinpath(f"melobot_cli_dev_run_{threading.get_native_id()}.signal")
    )

    try:
        observer.start()
        while True:
            retcode: int
            create_alive_sig()
            pre_handlers: list | None = None
            retcodes: list[int] = []

            with subprocess.Popen(
                cmd,
                env=os.environ,
                cwd=cwd,
                stdin=sys.stdin,
                stdout=sys.stdout,
                stderr=sys.stderr,
            ) as proc:

                if reload_signal.is_set():
                    reload_signal.clear()

                pre_handlers = set_signal_handler(proc, retcodes)
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                    futures: list[concurrent.futures.Future] = [
                        executor.submit(proc.wait),
                        executor.submit(reload_signal.wait),
                    ]
                    _, _ = concurrent.futures.wait(
                        futures, return_when=concurrent.futures.FIRST_COMPLETED
                    )

                    if reload_signal.is_set():
                        clear_alive_sig()
                        proc.wait()
                        retcode = ExitCode.RESTART.value
                    else:
                        # 避免一直等待导致线程池无法关闭
                        reload_signal.set()
                        retcode = proc.returncode

            if len(retcodes):
                retcode = retcodes[0]

            if pre_handlers is not None:
                clear_signal_handler(pre_handlers)

            if CLI_LAST_EXIT_CODE in os.environ:
                os.environ.pop(CLI_LAST_EXIT_CODE)

            if retcode == ExitCode.NORMAL.value:
                break

            if retcode == ExitCode.RESTART.value:
                print("\n>>> [mb-cli] 正在重启 Bot 主程序\n")
                os.environ[CLI_LAST_EXIT_CODE] = str(ExitCode.RESTART.value)
                continue

            if retcode == ExitCode.ERROR.value:
                break

            print()
            print(f">>> [mb-cli] Bot 主程序返回了意料之外的退出码: {retcode}")
            print(">>> [mb-cli] 若提示“已安全停止运行”，则无需关注此警告")
            break

    finally:
        clear_alive_sig()
        observer.stop()
        observer.join()
        shutil.rmtree(tmp_dir)


def create_alive_sig() -> None:
    with open(os.environ[CLI_RUN_ALIVE_FLAG], "wb"):
        pass


def clear_alive_sig() -> None:
    if os.path.exists(os.environ[CLI_RUN_ALIVE_FLAG]):
        os.remove(os.environ[CLI_RUN_ALIVE_FLAG])


def set_signal_handler(proc: subprocess.Popen, rets: list[int]) -> list:
    def signal_handler(*_: Any, **__: Any) -> None:
        # 重入安全
        clear_alive_sig()
        retcode = proc.wait()
        rets.clear()
        rets.append(retcode)

    pre_handlers = []
    pre_handlers.append(signal.getsignal(signal.SIGINT))
    pre_handlers.append(signal.getsignal(signal.SIGTERM))
    if sys.platform == "win32":
        pre_handlers.append(signal.getsignal(signal.SIGBREAK))

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    if sys.platform == "win32":
        signal.signal(signal.SIGBREAK, signal_handler)

    return pre_handlers


def clear_signal_handler(pre_handlers: list) -> None:
    signal.signal(signal.SIGINT, pre_handlers[0])
    signal.signal(signal.SIGTERM, pre_handlers[1])
    if sys.platform == "win32":
        signal.signal(signal.SIGBREAK, pre_handlers[2])


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
            f"部分功能需要额外的依赖。安装这些额外依赖：pip install 'melobot[cli]>={__version__}'"
        )
        sys.exit(1)
