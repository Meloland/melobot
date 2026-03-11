from argparse import Namespace
from pathlib import Path

from ...utils import get_module_filename
from . import __plugin__


def template_main(args: Namespace) -> None:
    template_root = Path(__file__).parent
    target_root: Path = args.target_root
    entry_filename = get_module_filename(__plugin__)

    entry_content = template_root.joinpath(entry_filename).read_text(encoding="utf-8")
    entry_content = entry_content.replace("VAR_PLUGIN_NAME_S", "_".join(args.name_parts))
    target_root.joinpath(entry_filename).write_text(entry_content, encoding="utf-8")
    print(f"扩展 {args.root_name} 已创建")
