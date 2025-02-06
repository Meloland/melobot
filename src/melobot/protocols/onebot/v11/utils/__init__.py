from types import ModuleType

from typing_extensions import Any

from melobot.utils.common import DeprecatedLoader as _DeprecatedLoader

from .check import (
    AtMsgChecker,
    GroupMsgChecker,
    GroupRole,
    LevelRole,
    MsgChecker,
    MsgCheckerFactory,
    PrivateMsgChecker,
    get_group_role,
    get_level_role,
)

_LOADER = _DeprecatedLoader(
    __name__,
    {
        "Checker": ("melobot.utils.check", "Checker", "3.1.1"),
        "Matcher": ("melobot.utils.match", "Matcher", "3.1.1"),
        "ParseArgs": ("melobot.utils.parse", "CmdArgs", "3.1.1"),
        "Parser": ("melobot.utils.parse", "Parser", "3.1.1"),
        "ContainMatcher": ("melobot.utils.match", "ContainMatcher", "3.1.1"),
        "EndMatcher": ("melobot.utils.match", "EndMatcher", "3.1.1"),
        "FullMatcher": ("melobot.utils.match", "FullMatcher", "3.1.1"),
        "RegexMatcher": ("melobot.utils.match", "RegexMatcher", "3.1.1"),
        "StartMatcher": ("melobot.utils.match", "StartMatcher", "3.1.1"),
        "CmdArgFormatter": ("melobot.utils.parse", "CmdArgFormatter", "3.1.1"),
        "CmdParser": ("melobot.utils.parse", "CmdParser", "3.1.1"),
        "CmdParserFactory": ("melobot.utils.parse", "CmdParserFactory", "3.1.1"),
        "FormatInfo": ("melobot.utils.parse", "CmdArgFormatInfo", "3.1.1"),
    },
)


def __getattr__(name: str) -> Any:
    return _LOADER.get(name)
