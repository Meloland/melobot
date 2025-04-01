from __future__ import annotations

import base64
import json
import re
import warnings
from collections.abc import Mapping
from itertools import chain, zip_longest

from pydantic import BaseModel, Discriminator, Tag, create_model
from typing_extensions import (
    Annotated,
    Any,
    Generic,
    Literal,
    Match,
    NotRequired,
    Self,
    Sequence,
    TypedDict,
    TypeVar,
    cast,
    final,
    get_args,
    overload,
)

from melobot.adapter import content as mbcontent

SegTypeT = TypeVar("SegTypeT", bound=str, default=Any)
SegDataT = TypeVar("SegDataT", bound=Mapping[str, Any], default=Any)


def cq_filter_text(s: str) -> str:
    """cq 文本过滤函数

    可从 cq 字符串中过滤出纯文本消息部分

    :param s: cq 字符串
    :return: 纯文本消息部分
    """
    regex = re.compile(r"\[CQ:.*?\]")
    return regex.sub("", s)


def cq_escape(text: str) -> str:
    """cq 字符串特殊符号转义

    如：将 "&" 转义为 "&amp;"

    :param text: 需要转义的 cq 字符串
    :return: 转义特殊符号后的 cq 字符串
    """
    return (
        text.replace("&", "&amp;").replace("[", "&#91;").replace("]", "&#93;").replace(",", "&#44;")
    )


def cq_anti_escape(text: str) -> str:
    """cq 字符串特殊符号逆转义

    如：将 "&amp;" 逆转义为 "&"

    :param text: 需要逆转义的 cq 字符串
    :return: 逆转义特殊符号后的 cq 字符串
    """
    return (
        text.replace("&#44;", ",").replace("&#93;", "]").replace("&#91;", "[").replace("&amp;", "&")
    )


def _cq_to_dicts(s: str) -> list[dict[str, Any]]:
    cq_texts: list[str] = []

    def replace_func(m: Match) -> str:
        s, e = m.regs[0]
        cq_texts.append(m.string[s:e])
        return "\u0000"

    cq_regex = re.compile(r"\[CQ:.*?\]")

    no_cq_str = cq_regex.sub(replace_func, s)
    pure_texts = map(
        lambda x: f"[CQ:text,text={x}]" if x != "" else x,
        no_cq_str.split("\u0000"),
    )
    cq_entity_str: str = "".join(
        chain.from_iterable(zip_longest(pure_texts, cq_texts, fillvalue=""))
    )

    cq_entity: list[str] = cq_entity_str.split("]")[:-1]
    dicts: list[dict[str, Any]] = []

    for e in cq_entity:
        cq_parts = e.split(",")
        cq_type = cq_parts[0][4:]
        cq_data: dict[str, Any] = {}

        for param_pair in cq_parts[1:]:
            name, val = param_pair.split("=", maxsplit=1)
            if len(cq_entity) == 1 and cq_type == "text":
                cq_data[name] = val
            else:
                cq_data[name] = cq_anti_escape(val)

        if cq_type == "node" and "content" in cq_data and isinstance(cq_data["content"], str):
            cq_data["content"] = [
                Segment.resolve(seg_dict["type"], seg_dict["data"])
                for seg_dict in _cq_to_dicts(cq_data["content"])
            ]

        dicts.append({"type": cq_type, "data": cq_data})

    return dicts


def _segment_to_cq(type: str, data: dict[str, Any]) -> str:
    if type == "text":
        return cast(str, data["text"])

    if type != "node":
        params = ",".join(f"{k}={cq_escape(str(v))}" for k, v in data.items())
    else:
        param_list: list[str] = []
        for k, v in data.items():
            if k == "content":
                inner_cq = "".join(
                    _segment_to_cq(inner_seg.type, inner_seg.data) for inner_seg in v
                )
                param_list.append(f"{k}={cq_escape(inner_cq)}")
            else:
                param_list.append(f"{k}={cq_escape(str(v))}")
        params = ",".join(param_list)

    s = f"[CQ:{type}"
    if params != "":
        s += f",{params}"
    s += "]"
    return s


def base64_encode(data: bytes) -> str:
    code = "base64://"
    code += base64.b64encode(data).decode("utf-8")
    return code


def segs_to_contents(message: Sequence[Segment]) -> list[mbcontent.Content]:
    contents: list[mbcontent.Content] = []
    for seg in message:
        if isinstance(seg, TextSegment):
            contents.append(mbcontent.TextContent(seg.data["text"]))

        elif isinstance(seg, ImageRecvSegment):
            contents.append(mbcontent.ImageContent(name=seg.data["file"], url=str(seg.data["url"])))

        elif isinstance(seg, RecordRecvSegment):
            contents.append(mbcontent.VoiceContent(name=seg.data["file"], url=str(seg.data["url"])))

        elif isinstance(seg, VideoRecvSegment):
            contents.append(mbcontent.VideoContent(name=seg.data["file"], url=str(seg.data["url"])))

        elif isinstance(seg, AtSegment):
            contents.append(
                mbcontent.ReferContent(prompt=str(seg.data["qq"]), flag=seg.data["qq"], contents=())
            )

        elif isinstance(seg, ShareSegment):
            contents.append(
                mbcontent.ResourceContent(name=seg.data["title"], url=str(seg.data["url"]))
            )

        else:
            continue

    return contents


def contents_to_segs(contents: Sequence[mbcontent.Content]) -> list[Segment]:
    segments: list[Segment] = []
    for c in contents:
        if isinstance(c, mbcontent.TextContent):
            segments.append(TextSegment(c.text))

        elif isinstance(c, mbcontent.ImageContent):
            if c.val:
                file = base64_encode(c.val)
                segments.append(ImageSendSegment(file=file, cache=0))
            else:
                segments.append(ImageSendSegment(file=cast(str, c.url), cache=0))

        elif isinstance(c, mbcontent.VoiceContent):
            if c.val:
                file = base64_encode(c.val)
                segments.append(RecordSendSegment(file=file, cache=0))
            else:
                segments.append(RecordSendSegment(file=cast(str, c.url), cache=0))

        elif isinstance(c, mbcontent.AudioContent):
            if c.val:
                file = base64_encode(c.val)
                segments.append(RecordSendSegment(file=file, cache=0))
            else:
                segments.append(RecordSendSegment(file=cast(str, c.url), cache=0))

        elif isinstance(c, mbcontent.VideoContent):
            if c.val:
                file = base64_encode(c.val)
                segments.append(VideoSendSegment(file=file, cache=0))
            else:
                segments.append(VideoSendSegment(file=cast(str, c.url), cache=0))

        elif isinstance(c, mbcontent.MediaContent):
            if c.val:
                segments.append(TextSegment(f"[OneBot v11 media: {c.name}]"))
            else:
                segments.append(ShareSegment(url=cast(str, c.url), title=c.name))

        elif isinstance(c, mbcontent.FileContent):
            segments.append(TextSegment(repr(c)))

        elif isinstance(c, mbcontent.ReferContent):
            segments.append(TextSegment(repr(c)))

        elif isinstance(c, mbcontent.ResourceContent):
            segments.append(ShareSegment(url=c.url, title=c.name))

        else:
            continue

    return segments


TypeT = TypeVar("TypeT", bound=str, default=Any)
DataT = TypeVar("DataT", bound=Mapping[str, Any], default=Any)


class Segment(Generic[SegTypeT, SegDataT]):

    class Model(BaseModel):
        type: str
        data: dict

    def __init__(self, seg_type: SegTypeT, **seg_data: Any) -> None:
        self.raw = {"type": seg_type, "data": seg_data}
        self._model = self.Model(
            type=seg_type,
            data={k: v for k, v in seg_data.items() if v is not None},
        )

    @classmethod
    @final
    def add_type(
        cls, seg_type_hint: Any, seg_data_hint: type[DataT]
    ) -> type[CustomSegCls[Any, DataT]]:
        from melobot.typ import is_subhint

        if cls is not Segment:
            raise ValueError(f"只能使用 {Segment.__name__} 类的 {Segment.add_type.__name__} 方法")
        if not is_subhint(seg_type_hint, Literal):
            raise ValueError("新消息段的类型标注必须为 Literal")
        if not is_subhint(seg_data_hint, TypedDict):
            raise ValueError("新消息段的类型标注必须为 TypedDict")

        hint_args = get_args(seg_type_hint)
        if len(hint_args) != 1:
            raise ValueError("新消息段的类型标注必须只有一个字面量")

        type_name: str = hint_args[0]
        stand_name = type_name.lower().capitalize()
        type_classname = f"{stand_name}Segment"
        type_dataname = f"_{stand_name}Data"

        if type_classname in {subcls.__name__ for subcls in cls.__subclasses__()}:
            raise ValueError(f"类型为 {type_name} 的消息段类型已经存在")

        seg_cls = type(
            type_classname,
            (CustomSegCls,),
            {
                "Model": create_model(
                    type_dataname,
                    type=(seg_type_hint, ...),
                    data=(seg_data_hint, ...),
                ),
                "SegTypeVal": type_name,
            },
        )
        setattr(
            seg_cls,
            Segment.resolve.__name__,
            lambda _, seg_data: seg_cls(**seg_data),
        )
        return seg_cls

    @property
    def type(self) -> SegTypeT:
        return cast(SegTypeT, self._model.type)

    @property
    def data(self) -> SegDataT:
        return cast(SegDataT, self._model.data)

    @classmethod
    def resolve(cls, seg_type: Any, seg_data: Any) -> Segment:
        cls_name = f"{seg_type.lower().capitalize()}Segment"
        cls_map = {
            subcls.__name__: subcls
            for subcls in cls.__subclasses__() + CustomSegCls.__subclasses__()
        }
        if cls_name in cls_map:
            return cls_map[cls_name].resolve(seg_type, seg_data)
        return cls(seg_type, **seg_data)

    @classmethod
    def __resolve_cq__(cls, cq_str: str) -> list[Segment]:
        dicts = _cq_to_dicts(cq_str)
        segs = [cls.resolve(dic["type"], dic["data"]) for dic in dicts]
        return segs

    def to_cq(self) -> str:
        return _segment_to_cq(self.type, cast(dict[str, Any], self.data))

    def to_dict(self, force_str: bool = False) -> dict[str, Any]:
        dic: dict[str, Any] = self._model.model_dump()
        if not force_str:
            return dic

        for k, v in dic["data"].items():
            dic["data"][k] = str(v)
        return dic

    def to_json(self, force_str: bool = False) -> str:
        return json.dumps(self.to_dict(force_str), ensure_ascii=False)


class CustomSegCls(Segment[TypeT, DataT]):
    SegTypeVal: Any

    def __init__(self, **seg_data: Any) -> None:
        super().__init__(self.__class__.SegTypeVal, **seg_data)


class _TextData(TypedDict):
    text: str


class TextSegment(Segment[Literal["text"], _TextData]):

    class Model(BaseModel):
        type: Literal["text"]
        data: _TextData

    def __init__(self, text: str, **kwargs: Any) -> None:
        super().__init__("text", text=text, **kwargs)

    @classmethod
    def resolve(cls, seg_type: Literal["text"], seg_data: _TextData) -> Self:
        return cls(**seg_data)

    def to_cq(self, escape: bool = False) -> str:
        text = super().to_cq()
        if escape:
            text = cq_escape(text)
        return text


class _FaceData(TypedDict):
    id: int


class FaceSegment(Segment[Literal["face"], _FaceData]):

    class Model(BaseModel):
        type: Literal["face"]
        data: _FaceData

    def __init__(self, id: int, **kwargs: Any) -> None:
        super().__init__("face", id=id, **kwargs)

    @classmethod
    def resolve(cls, seg_type: Literal["face"], seg_data: _FaceData) -> Self:
        return cls(**seg_data)


class _ImageSendData(TypedDict):
    file: str
    type: NotRequired[Literal["flash"]]
    cache: NotRequired[Literal[0, 1]]
    proxy: NotRequired[Literal[0, 1]]
    timeout: NotRequired[int]


class _ImageRecvData(TypedDict):
    file: str
    type: NotRequired[Literal["flash"]]
    url: str


class ImageSegment(Segment[Literal["image"], _ImageSendData | _ImageRecvData]):

    class Model(BaseModel):
        type: Literal["image"]
        data: _ImageSendData | _ImageRecvData

    @overload
    def __init__(
        self,
        *,
        file: str,
        type: Literal["flash"] | None = None,
        cache: Literal[0, 1] | None = None,
        proxy: Literal[0, 1] | None = None,
        timeout: int | None = None,
    ) -> None: ...

    @overload
    def __init__(self, *, file: str, url: str, type: Literal["flash"] | None = None) -> None: ...

    def __init__(self, **kv_pairs: Any) -> None:
        super().__init__("image", **kv_pairs)

    @classmethod
    def resolve(
        cls,
        seg_type: Literal["image"],
        seg_data: _ImageSendData | _ImageRecvData,
    ) -> ImageSegment:
        if "url" in seg_data:
            return ImageRecvSegment(**seg_data)
        return ImageSendSegment(**seg_data)


class ImageSendSegment(ImageSegment):
    def __init__(
        self,
        *,
        file: str,
        type: Literal["flash"] | None = None,
        cache: Literal[0, 1] | None = None,
        proxy: Literal[0, 1] | None = None,
        timeout: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(file=file, type=type, cache=cache, proxy=proxy, timeout=timeout, **kwargs)

    data: _ImageSendData


class ImageRecvSegment(ImageSegment):
    def __init__(
        self,
        *,
        file: str,
        url: str,
        type: Literal["flash"] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(file=file, url=url, type=type, **kwargs)

    data: _ImageRecvData


class _RecordSendData(TypedDict):
    file: str
    magic: NotRequired[Literal[0, 1]]
    cache: NotRequired[Literal[0, 1]]
    proxy: NotRequired[Literal[0, 1]]
    timeout: NotRequired[int]


class _RecordRecvData(TypedDict):
    file: str
    magic: NotRequired[Literal[0, 1]]
    url: str


class RecordSegment(Segment[Literal["record"], _RecordSendData | _RecordRecvData]):

    class Model(BaseModel):
        type: Literal["record"]
        data: _RecordSendData | _RecordRecvData

    @overload
    def __init__(
        self,
        *,
        file: str,
        magic: Literal[0, 1] | None = None,
        cache: Literal[0, 1] | None = None,
        proxy: Literal[0, 1] | None = None,
        timeout: int | None = None,
    ) -> None: ...

    @overload
    def __init__(self, *, file: str, url: str, magic: Literal[0, 1] | None = None) -> None: ...

    def __init__(self, **kv_pairs: Any) -> None:
        super().__init__("record", **kv_pairs)

    @classmethod
    def resolve(
        cls, seg_type: Literal["record"], seg_data: _RecordSendData | _RecordRecvData
    ) -> RecordSegment:
        if "url" in seg_data:
            return RecordRecvSegment(**seg_data)
        return RecordSendSegment(**seg_data)


class RecordSendSegment(RecordSegment):
    def __init__(
        self,
        *,
        file: str | str,
        magic: Literal[0, 1] | None = None,
        cache: Literal[0, 1] | None = None,
        proxy: Literal[0, 1] | None = None,
        timeout: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            file=file, magic=magic, cache=cache, proxy=proxy, timeout=timeout, **kwargs
        )

    data: _RecordSendData


class RecordRecvSegment(RecordSegment):
    def __init__(
        self,
        *,
        file: str,
        url: str,
        magic: Literal[0, 1] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(file=file, url=url, magic=magic, **kwargs)

    data: _RecordRecvData


class _VideoSendData(TypedDict):
    file: str
    cache: NotRequired[Literal[0, 1]]
    proxy: NotRequired[Literal[0, 1]]
    timeout: NotRequired[int]


class _VideoRecvData(TypedDict):
    file: str
    url: str


class VideoSegment(Segment[Literal["video"], _VideoSendData | _VideoRecvData]):

    class Model(BaseModel):
        type: Literal["video"]
        data: _VideoSendData | _VideoRecvData

    @overload
    def __init__(
        self,
        *,
        file: str,
        cache: Literal[0, 1] | None = None,
        proxy: Literal[0, 1] | None = None,
        timeout: int | None = None,
    ) -> None: ...

    @overload
    def __init__(self, *, file: str, url: str) -> None: ...

    def __init__(self, **kv_pairs: Any) -> None:
        super().__init__("video", **kv_pairs)

    @classmethod
    def resolve(
        cls, seg_type: Literal["video"], seg_data: _VideoSendData | _VideoRecvData
    ) -> VideoSegment:
        if "url" in seg_data:
            return VideoRecvSegment(**seg_data)
        return VideoSendSegment(**seg_data)


class VideoSendSegment(VideoSegment):
    def __init__(
        self,
        *,
        file: str,
        cache: Literal[0, 1] | None = None,
        proxy: Literal[0, 1] | None = None,
        timeout: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(file=file, cache=cache, proxy=proxy, timeout=timeout, **kwargs)

    data: _VideoSendData


class VideoRecvSegment(VideoSegment):
    def __init__(self, *, file: str, url: str, **kwargs: Any) -> None:
        super().__init__(file=file, url=url, **kwargs)

    data: _VideoRecvData


class _AtData(TypedDict):
    qq: int | Literal["all"]


class AtSegment(Segment[Literal["at"], _AtData]):

    class Model(BaseModel):
        type: Literal["at"]
        data: _AtData

    def __init__(self, qq: int | Literal["all"], **kwargs: Any) -> None:
        super().__init__("at", qq=qq, **kwargs)

    @classmethod
    def resolve(cls, seg_type: Literal["at"], seg_data: _AtData) -> AtSegment:
        return cls(**seg_data)


class _RpsData(TypedDict): ...


class RpsSegment(Segment[Literal["rps"], _RpsData]):

    class Model(BaseModel):
        type: Literal["rps"]
        data: _RpsData

    def __init__(self, **kwargs: Any) -> None:
        super().__init__("rps", **kwargs)

    @classmethod
    def resolve(cls, seg_type: Literal["rps"], seg_data: _RpsData) -> RpsSegment:
        return cls()


class _DictData(TypedDict): ...


class DiceSegment(Segment[Literal["dice"], _DictData]):

    class Model(BaseModel):
        type: Literal["dice"]
        data: _DictData

    def __init__(self, **kwargs: Any) -> None:
        super().__init__("dice", **kwargs)

    @classmethod
    def resolve(cls, seg_type: Literal["dice"], seg_data: _DictData) -> DiceSegment:
        return cls()


class _ShakeData(TypedDict): ...


class ShakeSegment(Segment[Literal["shake"], _ShakeData]):

    class Model(BaseModel):
        type: Literal["shake"]
        data: _ShakeData

    def __init__(self, **kwargs: Any) -> None:
        super().__init__("shake", **kwargs)

    @classmethod
    def resolve(cls, seg_type: Literal["shake"], seg_data: _ShakeData) -> ShakeSegment:
        return cls()


class _PokeSendData(TypedDict):
    type: str
    id: int


class _PokeRecvData(TypedDict):
    type: str
    id: int
    name: int


class PokeSegment(Segment[Literal["poke"], _PokeSendData | _PokeRecvData]):

    class Model(BaseModel):
        type: Literal["poke"]
        data: _PokeSendData | _PokeRecvData

    @overload
    def __init__(self, *, type: str, id: int) -> None: ...

    @overload
    def __init__(self, *, type: str, id: int, name: int) -> None: ...

    def __init__(self, **kv_pairs: Any) -> None:
        super().__init__("poke", **kv_pairs)

    @classmethod
    def resolve(
        cls, seg_type: Literal["poke"], seg_data: _PokeSendData | _PokeRecvData
    ) -> PokeSegment:
        if "name" in seg_data:
            return PokeRecvSegment(**seg_data)  # type: ignore[call-arg]
        return PokeSendSegment(**seg_data)


class PokeSendSegment(PokeSegment):
    def __init__(self, type: str, id: int, **kwargs: Any) -> None:
        super().__init__(type=type, id=id, **kwargs)

    data: _PokeSendData


class PokeRecvSegment(PokeSegment):
    def __init__(self, type: str, id: int, name: int, **kwargs: Any) -> None:
        super().__init__(type=type, id=id, name=name, **kwargs)

    data: _PokeRecvData


class _AnonymousData(TypedDict):
    ignore: NotRequired[Literal[0, 1]]


class AnonymousSegment(Segment[Literal["anonymous"], _AnonymousData]):

    class Model(BaseModel):
        type: Literal["anonymous"]
        data: _AnonymousData

    def __init__(self, ignore: Literal[0, 1] | None = None, **kwargs: Any) -> None:
        super().__init__("anonymous", ignore=ignore, **kwargs)

    @classmethod
    def resolve(cls, seg_type: Literal["anonymous"], seg_data: _AnonymousData) -> AnonymousSegment:
        return cls(**seg_data)


class _ShareData(TypedDict):
    url: str
    title: str
    content: NotRequired[str]
    image: NotRequired[str]


class ShareSegment(Segment[Literal["share"], _ShareData]):

    class Model(BaseModel):
        type: Literal["share"]
        data: _ShareData

    def __init__(
        self,
        url: str,
        title: str,
        content: str | None = None,
        image: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__("share", url=url, title=title, content=content, image=image, **kwargs)

    @classmethod
    def resolve(cls, seg_type: Literal["share"], seg_data: _ShareData) -> ShareSegment:
        return cls(**seg_data)


class _ContactFriendData(TypedDict):
    type: Literal["qq"]
    id: int


class _ContactGroupData(TypedDict):
    type: Literal["group"]
    id: int


class ContactSegment(Segment[Literal["contact"], _ContactFriendData | _ContactGroupData]):

    class Model(BaseModel):
        type: Literal["contact"]
        data: _ContactFriendData | _ContactGroupData

    def __init__(self, type: Literal["qq", "group"], id: int, **kwargs: Any) -> None:
        super().__init__("contact", type=type, id=id, **kwargs)

    @classmethod
    def resolve(
        cls,
        seg_type: Literal["contact"],
        seg_data: _ContactFriendData | _ContactGroupData,
    ) -> ContactSegment:
        if seg_data["type"] == "qq":
            return ContactFriendSegment(**seg_data)  # type:ignore[misc]
        return ContactGroupSegment(**seg_data)  # type:ignore[misc]


class ContactFriendSegment(ContactSegment):
    def __init__(self, id: int, **kwargs: Any) -> None:
        super().__init__(type="qq", id=id, **kwargs)

    data: _ContactFriendData


class ContactGroupSegment(ContactSegment):
    def __init__(self, id: int, **kwargs: Any) -> None:
        super().__init__(type="group", id=id, **kwargs)

    data: _ContactGroupData


class _LocationData(TypedDict):
    lat: float
    lon: float
    title: NotRequired[str]
    content: NotRequired[str]


class LocationSegment(Segment[Literal["location"], _LocationData]):

    class Model(BaseModel):
        type: Literal["location"]
        data: _LocationData

    def __init__(
        self,
        lat: float,
        lon: float,
        title: str | None = None,
        content: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__("location", lat=lat, lon=lon, title=title, content=content, **kwargs)

    @classmethod
    def resolve(cls, seg_type: Literal["location"], seg_data: _LocationData) -> LocationSegment:
        return cls(**seg_data)


class _MusicData(TypedDict):
    type: Literal["qq", "163", "xm"]
    id: str


class _MusicCustomData(TypedDict):
    type: Literal["custom"]
    url: str
    audio: str
    title: str
    content: NotRequired[str]
    image: NotRequired[str]


class MusicSegment(Segment[Literal["music"], _MusicData | _MusicCustomData]):

    class Model(BaseModel):
        type: Literal["music"]
        data: _MusicData | _MusicCustomData

    @overload
    def __init__(self, *, type: Literal["qq", "163", "xm"], id: str) -> None: ...

    @overload
    def __init__(
        self,
        *,
        type: Literal["custom"],
        url: str,
        audio: str,
        title: str,
        content: str | None = None,
        image: str | None = None,
    ) -> None: ...

    def __init__(self, **kv_pairs: Any) -> None:
        super().__init__("music", **kv_pairs)

    @classmethod
    def resolve(
        cls, seg_type: Literal["music"], seg_data: _MusicData | _MusicCustomData
    ) -> MusicSegment:
        if seg_data["type"] == "custom":
            return MusicCustomSegment(**seg_data)
        return MusicPlatformSegment(**seg_data)


class MusicPlatformSegment(MusicSegment):
    def __init__(self, *, type: Literal["qq", "163", "xm"], id: str, **kwargs: Any) -> None:
        super().__init__(type=type, id=id, **kwargs)

    data: _MusicData


class MusicCustomSegment(MusicSegment):
    def __init__(
        self,
        *,
        type: Literal["custom"],
        url: str,
        audio: str,
        title: str,
        content: str | None = None,
        image: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            type=type,
            url=url,
            audio=audio,
            title=title,
            content=content,
            image=image,
            **kwargs,
        )

    data: _MusicCustomData


class _ReplyData(TypedDict):
    id: str


class ReplySegment(Segment[Literal["reply"], _ReplyData]):

    class Model(BaseModel):
        type: Literal["reply"]
        data: _ReplyData

    def __init__(self, id: str, **kwargs: Any) -> None:
        super().__init__("reply", id=id, **kwargs)

    @classmethod
    def resolve(cls, seg_type: Literal["reply"], seg_data: _ReplyData) -> ReplySegment:
        return cls(**seg_data)


class _ForwardData(TypedDict):
    id: str


class ForwardSegment(Segment[Literal["forward"], _ForwardData]):

    class Model(BaseModel):
        type: Literal["forward"]
        data: _ForwardData

    def __init__(self, id: str, **kwargs: Any) -> None:
        super().__init__("forward", id=id, **kwargs)

    @classmethod
    def resolve(cls, seg_type: Literal["forward"], seg_data: _ForwardData) -> ForwardSegment:
        return cls(**seg_data)


class _NodeReferData(TypedDict):
    id: str


class _NodeStdCustomData(TypedDict):
    user_id: int
    nickname: str


class _NodeStdCustomDataInterface(_NodeStdCustomData):
    content: list[Segment]


class _NodeGocqCustomData(TypedDict):
    uin: int
    name: str


class _NodeGocqCustomDataInterface(_NodeGocqCustomData):
    content: list[Segment]


class NodeSegment(
    Segment[
        Literal["node"],
        _NodeReferData | _NodeStdCustomDataInterface | _NodeGocqCustomDataInterface,
    ]
):

    class Model(BaseModel):
        type: Literal["node"]
        data: Annotated[
            Annotated[_NodeReferData, Tag("0")]
            | Annotated[_NodeStdCustomData, Tag("1")]
            | Annotated[_NodeGocqCustomData, Tag("2")],
            Discriminator(lambda data: "0" if "id" in data else "1" if "user_id" in data else "2"),
        ]

    @overload
    def __init__(self, *, id: str) -> None: ...

    @overload
    def __init__(
        self,
        *,
        uin: int,
        name: str,
        content: list[Segment] | list[dict],
        use_std: bool = False,
    ) -> None: ...

    def __init__(self, **kv_pairs: Any) -> None:
        std: bool = kv_pairs.pop("use_std")
        id: str | None = kv_pairs.pop("id", None)
        content = kv_pairs.pop("content")
        _content: list[Segment]
        if len(content) and isinstance(content[0], dict):
            _content = [Segment.resolve(seg_dic["type"], seg_dic["data"]) for seg_dic in content]
        else:
            _content = content

        if id:
            super().__init__("node", id=id)
            return

        if not std:
            super().__init__("node", uin=kv_pairs["uin"], name=kv_pairs["name"])
        else:
            super().__init__("node", user_id=kv_pairs["uin"], nickname=kv_pairs["name"])
        self.data["content"] = _content  # type: ignore[typeddict-unknown-key]

    @classmethod
    def resolve(
        cls,
        seg_type: Literal["node"],
        seg_data: _NodeReferData | _NodeStdCustomDataInterface | _NodeGocqCustomDataInterface,
    ) -> NodeSegment:
        if "id" in seg_data:
            return NodeReferSegment(**seg_data)
        if "user_id" in seg_data:
            return NodeStdCustomSegment(**seg_data)  # type: ignore[arg-type]
        return NodeGocqCustomSegment(**seg_data)  # type: ignore[arg-type]

    def to_dict(self, force_str: bool = False) -> dict[str, Any]:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            dic = super().to_dict(force_str=False)

        if "content" in self.data:
            dic["data"]["content"] = [
                s.to_dict(force_str) for s in self.data["content"]  # type: ignore[typeddict-item]
            ]

        if not force_str:
            return dic

        for k, v in dic["data"].items():
            if k != "content":
                dic["data"][k] = str(v)

        return dic


class NodeReferSegment(NodeSegment):
    def __init__(self, id: str, **kwargs: Any) -> None:
        super().__init__(id=id, **kwargs)

    data: _NodeReferData


class NodeStdCustomSegment(NodeSegment):
    def __init__(self, user_id: int, nickname: str, content: list[Segment], **kwargs: Any) -> None:
        super().__init__(uin=user_id, name=nickname, content=content, use_std=True, **kwargs)

    data: _NodeStdCustomDataInterface


class NodeGocqCustomSegment(NodeSegment):
    def __init__(self, uin: int, name: str, content: list[Segment], **kwargs: Any) -> None:
        super().__init__(uin=uin, name=name, content=content, use_std=False, **kwargs)

    data: _NodeGocqCustomDataInterface


class _XmlData(TypedDict):
    data: str


class XmlSegment(Segment[Literal["xml"], _XmlData]):

    class Model(BaseModel):
        type: Literal["xml"]
        data: _XmlData

    def __init__(self, data: str, **kwargs: Any) -> None:
        super().__init__("xml", data=data, **kwargs)

    @classmethod
    def resolve(cls, seg_type: Literal["xml"], seg_data: _XmlData) -> XmlSegment:
        return cls(**seg_data)


class _JsonData(TypedDict):
    data: str


class JsonSegment(Segment[Literal["json"], _JsonData]):

    class Model(BaseModel):
        type: Literal["json"]
        data: _JsonData

    def __init__(self, data: str, **kwargs: Any) -> None:
        super().__init__("json", data=data, **kwargs)

    @classmethod
    def resolve(cls, seg_type: Literal["json"], seg_data: _JsonData) -> JsonSegment:
        return cls(**seg_data)
