"""Cross platform melobot.protocols.onebot dependencies freshing"""

import os
from pathlib import Path

import toml

os.chdir(str(Path(__file__).parent.parent.absolute().resolve(strict=True)))
with open(r"pyproject.toml", "r", encoding="utf-8") as fp:
    pyproj_toml = toml.load(fp)


def main() -> None:
    except_groups = (
        pyproj_toml["tool"]["pdm"]["dev-dependencies"]
        | pyproj_toml["project"]["optional-dependencies"]
    )
    except_groups.pop("onebot")
    excepts = ",".join(except_groups)
    ret = os.system(f"pdm export -o onebot_requirements.txt --without {excepts}")
    if ret == 0:
        print("已刷新 protocols.onebot 的 requirements.txt")
    else:
        print("未能完成刷新 protocols.onebot 的 requirements.txt 的任务")


if __name__ == "__main__":
    main()
