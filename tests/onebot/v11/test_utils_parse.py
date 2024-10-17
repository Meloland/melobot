from asyncio import Queue

from melobot.ctx import LoggerCtx
from melobot.log import Logger
from melobot.protocols.onebot.v11.utils import CmdArgFormatter as Fmtter
from melobot.protocols.onebot.v11.utils import CmdParserFactory
from tests.base import *

_OUT_BUF = Queue()


async def test_parser():
    pf1 = CmdParserFactory(".", ["#", "$"])
    pf2 = CmdParserFactory([".", "*"], " ")

    p1 = pf1.get("test")
    assert (await p1.parse("as;dfja;j;f;ajf;")) is None
    assert (await p1.parse("\n\t .test 123")) is None
    assert (await p1.parse("\n\t .test123#123")) is None
    assert (await p1.parse("\n\t .test\t\n")).vals == []
    assert (await p1.parse("\n\t .test#456\n\t\r\n")).vals == ["456"]

    p2 = pf1.get(["test", "echo"])
    assert (await p2.parse(".test#asdjf;a#")).vals == ["asdjf;a"]
    assert (await p2.parse(".echo#")).vals == []

    with LoggerCtx().in_ctx(Logger()):
        p3 = pf1.get(
            ["test", "echo"],
            [
                Fmtter(
                    convert=lambda s: int(s),
                    validate=lambda i: 0 <= i <= 10,
                    src_desc="测试命令的重复次数",
                    src_expect="0-10 的数字",
                    default=5,
                    default_replace_flag="/",
                    convert_fail=lambda _: _OUT_BUF.put(True),
                    validate_fail=lambda _: _OUT_BUF.put(True),
                    arg_lack=lambda _: _OUT_BUF.put(True),
                ),
                Fmtter(
                    convert=lambda s: float(s),
                    validate=lambda f: 0.0 <= f <= 10.0,
                    src_desc="测试命令的间隔时间",
                    src_expect="0.0-10.0 的数字",
                    arg_lack=lambda _: _OUT_BUF.put(True),
                ),
            ],
        )
        await p3.parse(".test#123")
        _OUT_BUF.get_nowait()
        await p3.parse(".echo#/$")
        _OUT_BUF.get_nowait()
        await p3.parse(".echo#abc")
        _OUT_BUF.get_nowait()
        assert (await p3.parse(".test$10#2")).vals == [10, 2.0]
        assert (await p3.parse(".echo#/$8")).vals == [5, 8.0]

    p4 = pf2.get(["test", "echo"])
    assert (await p4.parse("\t\f\n\rasdfa\n\rfa .test 123   asjf;\n\rlaja\r\n")).vals == [
        "123",
        "asjf;\n\rlaja",
    ]
    assert (
        await p4.parse("\t\f\n\rasdfa\n\rfa *echo 456 asdaf;   asjf;\n\rlaja\r\n")
    ).vals == ["456", "asdaf;", "asjf;\n\rlaja"]
