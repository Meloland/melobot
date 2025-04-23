import sys
from pathlib import Path

sys.path.insert(0, Path(__file__).parent.parent.parent.joinpath("src").resolve().as_posix())
from melobot._render import get_rich_str
