import sys
from multiprocessing import SimpleQueue
from pathlib import Path

sys.path.insert(0, Path(__file__).parent.parent.resolve().as_posix())
from tests.mp.submod import main


def test_all(argv: list[str], mod_name: str) -> None:
    if sys.argv != argv:
        raise ValueError("测试中的 argv 不匹配")
    if globals()["__name__"] != mod_name:
        raise ValueError("测试中的模块名不匹配")
    main()


def simple_test() -> None:
    main()
