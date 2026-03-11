from argparse import Namespace
from pathlib import Path

from .templates.plugin.__action__ import template_main as create_plugin_template
from .utils import get_name_parts, is_valid_identifier


def main(args: Namespace) -> None:
    if args.name == "" or len(args.name) <= 0:
        print("请提供扩展名称")
        return
    if not is_valid_identifier(args.name):
        print(f"无效的扩展名称：{args.name!r}")
        print("扩展名称必须是一个有效的 Python 标识符，且不能是 Python 关键字")
        return

    args.name_parts = get_name_parts(args.name)
    if args.no_prefix:
        args.root_name = "_".join(args.name_parts)
    else:
        args.root_name = f"melobot-{args.type}-{'_'.join(args.name_parts)}"

    args.target_parent = Path(args.dir).absolute()
    path = args.target_parent.joinpath(args.root_name)
    if path.exists():
        raise FileExistsError(f"目录 {path} 已存在")
    path.mkdir(parents=True, exist_ok=False)
    args.target_root = path

    print(f"正在创建扩展，类型：{args.type}, 名称：{args.root_name}")
    print(f"目录：{args.target_root}", end="\n\n")

    match args.type:
        case "plugin":
            create_plugin_template(args)
        case _:
            print(f"未知的扩展类型：{args.type}")
