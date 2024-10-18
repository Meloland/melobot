import os
from pathlib import Path

import toml

os.chdir(str(Path(__file__).parent.parent.absolute().resolve(strict=True)))
with open(r"pyproject.toml", "r", encoding="utf-8") as fp:
    pyproj_toml = toml.load(fp)

except_groups = (
    pyproj_toml["tool"]["pdm"]["dev-dependencies"]
    | pyproj_toml["project"]["optional-dependencies"]
)


def get_nega_groups(*groups: str | None) -> str:
    gs = except_groups.copy()
    for g in groups:
        if g is not None:
            gs.pop(g)
    return ",".join(gs)


def main() -> None:
    ret = os.system(f"pdm export -o requirements.txt --without {get_nega_groups()}")
    if ret == 0:
        print("已刷新项目的 requirements.txt")
    else:
        print("未能完成刷新项目的 requirements.txt 的任务")

    ret = os.system(
        f"pdm export -o tests/requirements.txt --without {get_nega_groups('test', 'onebot')}"
    )
    if ret == 0:
        print("已刷新项目测试的 requirements.txt")
    else:
        print("未能完成刷新项目测试的 requirements.txt 的任务")

    ret = os.system(
        f"pdm export -o docs/requirements.txt --without {get_nega_groups('docs', 'onebot')}"
    )
    if ret == 0:
        print("已刷新项目文档构建的 requirements.txt")
    else:
        print("未能完成刷新项目文档构建的 requirements.txt 的任务")

    ret = os.system(
        f"pdm export -o onebot_requirements.txt --without {get_nega_groups('onebot')}"
    )
    if ret == 0:
        print("已刷新 protocols.onebot 的 requirements.txt")
    else:
        print("未能完成刷新 protocols.onebot 的 requirements.txt 的任务")
