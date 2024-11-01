from argparse import Namespace
from pathlib import Path

from melobot.plugin.load import PluginInitHelper


def main(args: Namespace) -> None:
    if not len(args.files):
        print("未提供插件目录参数")
        return

    p_dirs = set(Path(p_dir) for p_dir in args.files)
    PluginInitHelper.run_init(*p_dirs, load_depth=args.depth)
    print(f"已完成 {len(args.files)} 个插件的初始化")
