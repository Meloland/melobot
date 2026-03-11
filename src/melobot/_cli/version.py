from argparse import Namespace

from melobot import MetaInfo

__version__ = "0.1.0"


def main(arg: Namespace) -> None:
    print(f"{'mb (cli program)':23} {__version__}")
    print(f"{'melobot':23} {MetaInfo.ver}")
