"""
以模块运行模式启动 bot，可以将 bot 程序包装启动。
从而可以实现重启等功能
"""

import os
import pathlib
import subprocess
import sys

sys.path.append("..")
from melobot.meta import (
    EXIT_CLOSE,
    EXIT_ERROR,
    EXIT_RESTART,
    MODULE_MODE_FLAG,
    MODULE_MODE_SET,
)

w, h = os.get_terminal_size()


def banner_print(s: str) -> None:
    print("-" * w)
    print("[melobot 模块]：", s, sep="")
    print("-" * w)


if len(sys.argv) != 2:
    print("以模块模式运行时，必须有且只有一个命令行参数：bot 主程序路径")
    sys.exit(0)
bot_script_path = sys.argv[1]
cmd = f"{sys.executable} {bot_script_path}"
cwd = str(pathlib.Path.cwd().absolute().resolve(strict=True))
os.environ[MODULE_MODE_FLAG] = MODULE_MODE_SET

try:
    while True:
        ret = subprocess.run(
            cmd,
            env=os.environ,
            cwd=cwd,
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        if ret.returncode == EXIT_CLOSE:
            break
        elif ret.returncode == EXIT_RESTART:
            banner_print("正在重启 bot 程序")
            continue
        elif ret.returncode == EXIT_ERROR:
            break
        else:
            banner_print("以模块运行模式运行时，bot 主程序返回了无法处理的返回值")
            break
except KeyboardInterrupt:
    pass
