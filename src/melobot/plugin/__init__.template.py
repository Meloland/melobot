from os import listdir as _VAR1
from pathlib import Path as _VAR2
from typing import Any as _VAR3

from melobot.bot import get_bot as _VAR4
from melobot.plugin.load import plugin_get_attr as _VAR5

_VAR6 = _VAR2(__file__).parent
_VAR7 = set(fname.split(".")[0] for fname in _VAR1(_VAR6))


def __getattr__(name: str) -> _VAR3:
    if name in _VAR7 or name.startswith("_"):
        raise AttributeError
    return _VAR5(_VAR4, _VAR6.parts[-1], name)
