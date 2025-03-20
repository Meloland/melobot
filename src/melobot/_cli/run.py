import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from argparse import Namespace
from pathlib import Path

from typing_extensions import Any

from melobot._run import CLI_LAST_EXIT_CODE, CLI_RUN_ALIVE_FLAG, CLI_RUN_FLAG, ExitCode


def main(args: Namespace) -> None:
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
        tmp_dir.joinpath(f"melobot_cli_run_{threading.get_native_id()}.signal")
    )

    try:
        while True:
            retcode: int
            create_alive_sig()
            pre_handlers: list | None = None

            with subprocess.Popen(
                cmd,
                env=os.environ,
                cwd=cwd,
                stdin=sys.stdin,
                stdout=sys.stdout,
                stderr=sys.stderr,
            ) as proc:
                pre_handlers = set_signal_handler()
                retcode = proc.wait()

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
        shutil.rmtree(tmp_dir)


def create_alive_sig() -> None:
    with open(os.environ[CLI_RUN_ALIVE_FLAG], "wb"):
        pass


def clear_alive_sig() -> None:
    if os.path.exists(os.environ[CLI_RUN_ALIVE_FLAG]):
        os.remove(os.environ[CLI_RUN_ALIVE_FLAG])


def set_signal_handler() -> list:
    def signal_handler(*_: Any, **__: Any) -> None:
        # 重入安全
        clear_alive_sig()

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
