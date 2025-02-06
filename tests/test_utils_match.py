from melobot.typ import LogicMode
from melobot.utils.match import (
    ContainMatcher,
    EndMatcher,
    FullMatcher,
    RegexMatcher,
    StartMatcher,
)
from tests.base import *


async def test_matcher():
    assert await ContainMatcher("123").match("sadfa12345")
    assert not await ContainMatcher("123").match("ajdflja12s;djf3")
    assert await ContainMatcher(["12345", "asdjfajf;s"]).match("asdjf;aj12345asdfj")
    assert await ContainMatcher(["12345", "789"], LogicMode.AND).match(
        "123456sdf;da789as;jf"
    )

    assert await EndMatcher("123").match("sadfa123")
    assert not await EndMatcher("123").match("sadfa12345")

    assert await FullMatcher("123").match("123")
    assert not await FullMatcher("123").match("12345")

    assert await RegexMatcher(r"\d+").match("12345")
    assert not await RegexMatcher(r"[A-Z]+").match("abc123")

    assert await StartMatcher("123").match("123sadfa")
    assert not await StartMatcher("123").match("sadfa12345")
