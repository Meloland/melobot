"""Cross platform melobot dependencies freshing"""

import os
from pathlib import Path

import toml

os.chdir(str(Path(__file__).parent.absolute().resolve(strict=True)))
with open(r"pyproject.toml", "r", encoding="utf-8") as fp:
    pyproj_toml = toml.load(fp)


def main():
    if os.path.exists("pdm.lock"):
        os.remove("pdm.lock")
        print("已移除依赖锁文件，准备重新生成")
    dev_groups = ",".join(pyproj_toml["tool"]["pdm"]["dev-dependencies"])
    ret = os.system(
        f"pdm update && pdm export -o requirements.txt --without {dev_groups}"
    )
    if ret == 0:
        print("已重新生成锁文件和 requirements.txt")
    else:
        print("未能完成刷新依赖操作")


if __name__ == "__main__":
    main()
