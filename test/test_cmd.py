from init import TESTER, send_test
import pytest


@pytest.mark.asyncio
async def test_cmd():
    res = await send_test("~echo#Hello MeloBot", isPrivate=False)
    assert res.msg.text == "Hello MeloBot"


@pytest.mark.asyncio
async def test_multi_cmd():
    res_list = await send_test("~echo#123~echo#456", isPrivate=True, respNum=2)
    assert res_list[0].msg.text == "123"
    assert res_list[1].msg.text == "456"


@pytest.mark.asyncio
async def test_non_cmd():
    res = await send_test("~#~asdf#adf~#~~##adsf~###~~~asdfasdf#asdf~#~#~", allTimeout=5)
    assert res is None
    res = await send_test("###~~~~##~#~##~#~#~####~~~~##", allTimeout=5)


@pytest.mark.asyncio
async def test_wrong_cmd():
    res = await send_test("~asjdlfjl#ajflja")
    assert res is None