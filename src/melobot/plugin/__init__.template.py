# pylint: disable=invalid-name
from os import listdir as _VAR1
from pathlib import Path as _VAR2
from typing import Any as _VAR3

from melobot import get_bot as _VAR4

_VAR5 = _VAR2(__file__).parent
_VAR6 = set(fname.split(".")[0] for fname in _VAR1(_VAR5))
_VAR7 = _VAR5.parts[-1]


def __getattr__(_VAR8: str) -> _VAR3:
    if _VAR8 in _VAR6 or _VAR8.startswith("_"):
        raise AttributeError
    _VAR9 = _VAR4().get_share(_VAR7, _VAR8)
    if _VAR9.static:
        return _VAR9.get()
    return _VAR9
