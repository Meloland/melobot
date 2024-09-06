"""Cross platform melobot dependencies freshing"""

import os
from pathlib import Path

import toml

os.chdir(str(Path(__file__).parent.parent.absolute().resolve(strict=True)))
with open(r"pyproject.toml", "r", encoding="utf-8") as fp:
    pyproj_toml = toml.load(fp)


def main() -> None:
    dev_groups = ",".join(pyproj_toml["tool"]["pdm"]["dev-dependencies"])
    ret = os.system(f"pdm export -o requirements.txt --without {dev_groups}")
    if ret == 0:
        print("已刷新 requirements.txt")
    else:
        print("未能完成刷新 requirements.txt 的任务")


if __name__ == "__main__":
    main()
