"""
以模块运行模式启动 bot，可以实现 bot 程序的重启
"""
import os
import sys
import subprocess
import pathlib

sys.path.append("..")
from melobot.meta import MODULE_MODE_FLAG, MODULE_MODE_SET, EXIT_CLOSE, EXIT_RESTART


if len(sys.argv) != 2:
    print("以模块模式运行时，必须有且只有一个命令行参数：bot 主程序路径")
    exit(0)
bot_script_path = sys.argv[1]
cmd = f"{sys.executable} {bot_script_path}"
cwd = str(pathlib.Path.cwd().absolute().resolve(strict=True))
os.environ[MODULE_MODE_FLAG] = MODULE_MODE_SET
w, h = os.get_terminal_size()

try:
    while True:
        ret = subprocess.run(cmd, env=os.environ, cwd=cwd, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)
        if ret.returncode == EXIT_CLOSE:
            break
        elif ret.returncode == EXIT_RESTART:
            print("-"*w)
            print("[melobot 模块]：正在重启 bot 程序")
            print("-"*w)
            continue
        else:
            raise RuntimeError("以模块运行模式运行时，bot 主程序返回了预期之外的返回值，无法处理")
except KeyboardInterrupt:
    pass
