import argparse

from . import dev, run, version
from .init import base as init
from .pinit import base as pinit


def tier1_main(args: argparse.Namespace) -> None:
    if args.version:
        version.main(args)
    else:
        parser.print_help()


parser = argparse.ArgumentParser(prog="mb", description="melobot 命令行工具", add_help=False)
parser.add_argument("-v", "--version", action="store_true", help="显示版本信息")
parser.add_argument("-h", "--help", action="help", help="打印此帮助信息并退出")
parser.set_defaults(_cmd_handler=tier1_main)
sub_parsers = parser.add_subparsers()

pinit_parser = sub_parsers.add_parser("pinit", help="运行插件入口初始化", add_help=False)
pinit_parser.add_argument("plugin_dirs", nargs="*", help="插件根目录路径")
pinit_parser.add_argument("-d", "--depth", type=int, default=1, help="运行初始化时的向上引用深度")
pinit_parser.add_argument("-h", "--help", action="help", help="打印此帮助信息并退出")
pinit_parser.set_defaults(_cmd_handler=pinit.main)

init_parser = sub_parsers.add_parser("init", help="按模板创建一个新的扩展", add_help=False)
init_parser.add_argument("-n", "--name", default="", help="扩展名称")
init_parser.add_argument("-t", "--type", choices=["plugin"], default="plugin", help="扩展类型")
init_parser.add_argument("-d", "--dir", default=".", help="创建扩展的目录路径")
init_parser.add_argument("--no-prefix", action="store_true", help="不为名称添加默认前缀")
init_parser.add_argument("-h", "--help", action="help", help="打印此帮助信息并退出")
init_parser.set_defaults(_cmd_handler=init.main)

run_parser = sub_parsers.add_parser(
    "run", help="以子进程模式运行 bot 主程序，且支持重启", add_help=False
)
run_parser.add_argument("entry_file", help="bot 程序入口 .py 文件路径")
run_parser.add_argument("-h", "--help", action="help", help="打印此帮助信息并退出")
run_parser.set_defaults(_cmd_handler=run.main)

dev_parser = sub_parsers.add_parser(
    "dev", help="以开发模式运行 bot 主程序，支持重启与自动重载", add_help=False
)
dev_parser.add_argument("entry_file", help="bot 程序入口 .py 文件路径")
dev_parser.add_argument("-w", "--watch", nargs="*", default=["."], help="需要监测的文件或目录路径")
dev_parser.add_argument("-h", "--help", action="help", help="打印此帮助信息并退出")
dev_parser.set_defaults(_cmd_handler=dev.main)


def main() -> None:
    args = parser.parse_args()
    args._cmd_handler(args)


if __name__ == "__main__":
    main()
