from argparse import Namespace

from melobot import MetaInfo

__version__ = "0.2.0"
PROG_NAME = "mb"


def main(arg: Namespace) -> None:
    print(f"{PROG_NAME + ' (cli program)':23} {__version__}")
    print(f"{MetaInfo.name:23} {MetaInfo.ver}")
