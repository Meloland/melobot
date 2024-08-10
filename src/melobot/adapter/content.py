import mimetypes
import pathlib
import urllib.parse

from ..exceptions import BotException, BotAdapterError
from ..types import (
    Any,
    AsyncCallable,
    BetterABC,
    TypeVar,
    abstractattr,
    abstractmethod,
    cast,
)

_URI_PROCESSOR_MAP: dict[str, AsyncCallable[[str], str | bytes]] = {}


def set_uri_processor(uri_type: str, processor: AsyncCallable[[str], Any]) -> None:
    if uri_type == "file":
        raise BotAdapterError("file 类型已存在内置处理器，不支持外部设定处理器")
    _URI_PROCESSOR_MAP[uri_type] = processor


class BotContentError(BotException):
    def __init__(self, msg: str):
        super().__init__(msg)


class AbstractContent(BetterABC):
    type: str = abstractattr()

    @property
    @abstractmethod
    def val(self) -> Any:
        raise NotImplementedError


Content_T = TypeVar("Content_T", bound=AbstractContent)


class TextContent(AbstractContent):
    def __init__(self, text: str) -> None:
        self.type = "text"
        self._val = text

    @property
    def val(self) -> str:
        return self._val


class BytesContent(AbstractContent):
    def __init__(self, val: bytes | bytearray) -> None:
        self.type = "bytes"
        self._val = val if isinstance(val, bytearray) else bytearray(val)

    @property
    def val(self) -> bytearray:
        return self._val


def _file_uri_to_path(uri: str, _class: type[pathlib.PurePath] = pathlib.Path):
    win_path = isinstance(_class(), pathlib.PureWindowsPath)
    uri_parsed = urllib.parse.urlparse(uri)
    uri_path_unquoted = urllib.parse.unquote(uri_parsed.path)
    if win_path and uri_path_unquoted.startswith("/"):
        res = _class(uri_path_unquoted[1:])
    else:
        res = _class(uri_path_unquoted)
    if not res.is_absolute():
        raise ValueError(
            "Invalid file uri {} : resulting path {} not absolute".format(uri, res)
        )
    return res


async def _load_from_uri(
    uri: str, fmode: str = "r", encoding: str | None = None
) -> str | bytes:
    try:
        if uri.startswith("file"):
            path = _file_uri_to_path(uri)
            with open(path, mode=fmode, encoding=encoding) as fp:
                return fp.read()
        else:
            processor = _URI_PROCESSOR_MAP.get(uri.split(":", 1)[0])
            if processor is None:
                return f"[Content: {uri}]"
            else:
                return await processor(uri)
    except Exception as e:
        raise BotContentError(f"值加载失败，uri 为：{uri}, 错误为：{e}")


class FileContent(AbstractContent):
    def __init__(
        self,
        *,
        name: str,
        uri: str,
        mimetype: str | None = None,
        bmode: bool = False,
        encoding: str | None = "utf-8",
    ) -> None:
        self.type = "file"
        self.name = name
        self.uri = uri
        self.fmode = "rb" if bmode else "r"
        self.encoding = encoding
        self._val: str | bytes

        if mimetype is None:
            self.mimetype, _ = mimetypes.guess_type(self.name)

    async def _load_val(self) -> None:
        if hasattr(self, "_val"):
            return

        self._val = await _load_from_uri(self.uri, self.fmode, self.encoding)

    @property
    async def val(self) -> str | bytes:
        await self._load_val()
        return self._val


class MediaContent(AbstractContent):
    def __init__(
        self,
        *,
        name: str,
        uri: str | None = None,
        raw: bytes | None = None,
        mimetype: str | None = None,
    ) -> None:
        self.name = name
        self.uri = uri

        if raw is not None:
            self._val = raw
        if mimetype is None:
            self.mimetype, _ = mimetypes.guess_type(self.name)

    async def _load_val(self) -> None:
        if hasattr(self, "_val"):
            return

        assert self.uri is not None
        self._val = cast(bytes, await _load_from_uri(self.uri, "rb"))

    @property
    async def val(self) -> bytes:
        await self._load_val()
        return self._val


class AudioContent(MediaContent):
    def __init__(
        self,
        *,
        name: str,
        uri: str | None = None,
        raw: bytes | None = None,
        mimetype: str | None = None,
    ) -> None:
        super().__init__(name=name, uri=uri, raw=raw, mimetype=mimetype)
        self.type = "audio"


class VideoContent(MediaContent):
    def __init__(
        self,
        *,
        name: str,
        uri: str | None = None,
        raw: bytes | None = None,
        mimetype: str | None = None,
    ) -> None:
        super().__init__(name=name, uri=uri, raw=raw, mimetype=mimetype)
        self.type = "video"
