import os
import shutil
import subprocess
import sys
import tempfile
import threading
from argparse import Namespace
from pathlib import Path

from melobot._run import CLI_LAST_EXIT_CODE, CLI_RUN_ALIVE_FLAG, CLI_RUN_FLAG
from melobot.typ import ExitCode

from ._signal import ShutdownState, clear_alive_sig, shutdown_signals
from .version import PROG_NAME


def main(args: Namespace) -> None:
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
        tmp_dir.joinpath(f"melobot_cli_run_{threading.get_native_id()}.signal")
    )

    state = ShutdownState()
    with shutdown_signals(state):
        try:
            while not state.requested:
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
                        retcode = proc.wait()
                    finally:
                        # 异常路径也先通知 bot 停止，再由 Popen 回收子进程。
                        clear_alive_sig()

                os.environ.pop(CLI_LAST_EXIT_CODE, None)

                if state.requested or retcode == ExitCode.NORMAL.value:
                    break

                if retcode == ExitCode.RESTART.value:
                    print(f"[{PROG_NAME}] 正在重启 Bot 主程序\n")
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
                shutil.rmtree(tmp_dir)


def create_alive_sig() -> None:
    with open(os.environ[CLI_RUN_ALIVE_FLAG], "wb"):
        pass
