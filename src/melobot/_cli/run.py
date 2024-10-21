import os
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

from melobot.bot.base import MELO_LAST_EXIT_SIGNAL, MELO_PKG_RUNTIME, BotExitSignal


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
    os.environ[MELO_PKG_RUNTIME] = "1"

    try:
        while True:
            ret = subprocess.run(
                cmd,
                env=os.environ,
                cwd=cwd,
                stdin=sys.stdin,
                stdout=sys.stdout,
                stderr=sys.stderr,
                check=False,
            )
            if MELO_LAST_EXIT_SIGNAL in os.environ:
                os.environ.pop(MELO_LAST_EXIT_SIGNAL)

            if ret.returncode == BotExitSignal.NORMAL_STOP.value:
                break
            if ret.returncode == BotExitSignal.RESTART.value:
                print("\n>>> [melobot module] 正在重启 bot 主程序\n")
                os.environ[MELO_LAST_EXIT_SIGNAL] = str(BotExitSignal.RESTART.value)
                continue
            if ret.returncode == BotExitSignal.ERROR.value:
                break
            print("\n>>> [melobot module] bot 主程序退出时返回了无法处理的返回值\n")
            break

    except KeyboardInterrupt:
        pass
