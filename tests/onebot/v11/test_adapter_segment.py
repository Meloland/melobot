from typing import Literal

from pydantic import ValidationError
from typing_extensions import TypedDict

from melobot.protocols.onebot.v11.adapter import segment as seg
from tests.base import *


async def test_smart_union():
    s = seg.ImageSegment(file="12345678")
    s = seg.ImageSegment(file="12345678.jpg", url="https://example.com/12345678.jpg")
    s = seg.ContactSegment(type="qq", id=12345678)
    s = seg.ContactSegment(type="group", id=12345678)
    s = seg.MusicSegment(
        type="custom",
        url="https://example.com/music.mp3",
        audio="https://example.com/audio.mp3",
        title="music",
    )


async def test_type_and_data():
    s = seg.Segment("my", key="123")
    assert s.type == "my"
    assert s.data == {"key": "123"}


async def test_add_type():
    SType = seg.Segment.add_type(Literal["MyS"], TypedDict("MyData", {"key": str}))
    s = SType(key="123")
    assert s.type == "MyS"
    assert s.data == {"key": "123"}
    assert SType in seg.Segment.__subclasses__()
    with pt.raises(ValidationError):
        SType(key=123)


async def test_serialize_and_deserialize():
    sl1 = seg.Segment.__resolve_cq__("12345[CQ:image,file=12345678.jpg]123456")
    sl2 = seg.Segment.__resolve_cq__(
        "123&#91;45[CQ:node,user_id=10001000,nickname=某人,content=&#91;CQ:face&#44;id=123&#93;哈喽～]12345"
    )

    s3 = seg.ImageSegment(file="12345678")
    s4 = seg.RpsSegment()
    s5 = seg.Segment.__resolve_cq__("12345")[0]
    s6 = seg.Segment.__resolve_cq__("[CQ:image,file=12345678.jpg]")[0]
    s7 = seg.AtSegment(15742)
    s8 = seg.Segment.__resolve_cq__("")

    assert s8 == []

    assert sl1[0].to_dict() == {"type": "text", "data": {"text": "12345"}}
    assert sl1[1].to_dict() == {"type": "image", "data": {"file": "12345678.jpg"}}
    assert sl1[2].to_dict() == {"type": "text", "data": {"text": "123456"}}
    assert sl2[0].to_dict() == {"type": "text", "data": {"text": "123[45"}}
    assert sl2[1].to_dict() == {
        "type": "node",
        "data": {
            "user_id": 10001000,
            "nickname": "某人",
            "content": [
                {"type": "face", "data": {"id": 123}},
                {"type": "text", "data": {"text": "哈喽～"}},
            ],
        },
    }
    assert sl2[1].to_dict(force_str=True) == {
        "type": "node",
        "data": {
            "user_id": "10001000",
            "nickname": "某人",
            "content": [
                {"type": "face", "data": {"id": "123"}},
                {"type": "text", "data": {"text": "哈喽～"}},
            ],
        },
    }
    assert s7.to_dict(force_str=True) == {"type": "at", "data": {"qq": "15742"}}
    assert sl2[2].to_dict() == {"type": "text", "data": {"text": "12345"}}
    assert s5.to_dict() == {"type": "text", "data": {"text": "12345"}}
    assert s6.to_dict() == {"type": "image", "data": {"file": "12345678.jpg"}}

    assert s3.to_cq() == "[CQ:image,file=12345678]"
    assert s4.to_cq() == "[CQ:rps]"
    assert "".join(s.to_cq() for s in sl1) == "12345[CQ:image,file=12345678.jpg]123456"
    assert (
        sl2[0].to_cq(escape=True) + sl2[1].to_cq() + sl2[2].to_cq()
        == "123&#91;45[CQ:node,user_id=10001000,nickname=某人,content=&#91;CQ:face&#44;id=123&#93;哈喽～]12345"
    )
    assert s5.to_cq() == "12345"
    assert s6.to_cq() == "[CQ:image,file=12345678.jpg]"

    assert s6.to_json() == '{"type": "image", "data": {"file": "12345678.jpg"}}'
