"""Cross platform Sphinx doc build, called by pdm command."""

import os
import sys
from pathlib import Path

os.chdir(str(Path(__file__).parent.absolute().resolve(strict=True)))


def main():
    if sys.platform != "win32":
        os.system("make html")
    else:
        os.system("make.bat html")


if __name__ == "__main__":
    main()
