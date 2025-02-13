from os import listdir as _VAR1
from pathlib import Path as _VAR2
from typing import Any as _VAR3

from melobot.plugin.load import plugin_get_attr as _VAR4

_VAR5 = _VAR2(__file__).parent
_VAR6 = set(fname.split(".")[0] for fname in _VAR1(_VAR5))
_VAR7 = _VAR5.parts[-1]


def __getattr__(name: str) -> _VAR3:
    return _VAR4(_VAR7, name, _VAR6)
