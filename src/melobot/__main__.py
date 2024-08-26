import argparse
import sys

from melobot._cli import pinit, run

parser = argparse.ArgumentParser(prog="mb-cli", description="melobot 命令行工具")
sub_parsers = parser.add_subparsers()

pinit_parser = sub_parsers.add_parser("pinit", help="运行 melobot 插件自动初始化")
pinit_parser.add_argument("files", nargs="*", help="插件根目录路径")
pinit_parser.add_argument(
    "--depth", "-d", type=int, default=1, help="插件初始化的向上引用深度"
)
pinit_parser.set_defaults(_cmd_handler=pinit.main)

run_parser = sub_parsers.add_parser(
    "run", help="以子进程模式运行 melobot bot 主程序，且支持重启"
)
run_parser.add_argument("entry_file", help="bot 程序入口 .py 文件路径")
run_parser.set_defaults(_cmd_handler=run.main)

args = parser.parse_args()
if len(sys.argv) > 1:
    args._cmd_handler(args)  # pylint: disable=protected-access
else:
    print("无命令参数，mb-cli 已结束运行，使用 -h 命令参数获取帮助信息")
