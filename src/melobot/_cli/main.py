import argparse
import sys

from . import dev, pinit, run

parser = argparse.ArgumentParser(prog="mb", description="melobot 命令行工具")
sub_parsers = parser.add_subparsers()

pinit_parser = sub_parsers.add_parser("pinit", help="运行 melobot 插件入口初始化")
pinit_parser.add_argument("files", nargs="*", help="插件根目录路径")
pinit_parser.add_argument("--depth", "-d", type=int, default=1, help="运行初始化时的向上引用深度")
pinit_parser.set_defaults(_cmd_handler=pinit.main)

run_parser = sub_parsers.add_parser("run", help="以子进程模式运行 melobot bot 主程序，且支持重启")
run_parser.add_argument("entry_file", help="bot 程序入口 .py 文件路径")
run_parser.set_defaults(_cmd_handler=run.main)

dev_parser = sub_parsers.add_parser(
    "dev", help="以开发模式运行 melobot bot 主程序，支持重启与自动重载"
)
dev_parser.add_argument("entry_file", help="bot 程序入口 .py 文件路径")
dev_parser.add_argument("--watch", nargs="*", default=["."], help="需要监测的文件或目录路径")
dev_parser.set_defaults(_cmd_handler=dev.main)


def main() -> None:
    args = parser.parse_args()
    if len(sys.argv) > 1:
        args._cmd_handler(args)
    else:
        print("无命令选项，已结束运行。使用 -h 或 --help 选项获取帮助信息")


if __name__ == "__main__":
    main()
