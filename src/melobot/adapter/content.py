import pathlib
import urllib.parse

import aiohttp

from ..exceptions import BotException, BotValidateError
from ..typing import Any, BetterABC, TypeVar, abstractattr, abstractmethod


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


class FileContent(AbstractContent):
    def __init__(self, *, name: str, uri: str, mimetype: str | None = None) -> None:
        self.type = "file"
        self.name = name
        self.uri = uri
        self.mimetype = mimetype

    @property
    def val(self) -> str:
        return self.uri


class AbstractMediaContent(AbstractContent):
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
        self.mimetype = mimetype
        if raw is not None:
            self._val = raw

    def _file_uri_to_path(self, uri: str, _class: type[pathlib.PurePath] = pathlib.Path):
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

    async def _load_val(self) -> None:
        if hasattr(self, "_val"):
            return

        assert self.uri is not None
        try:
            if self.uri.startswith("http"):
                async with aiohttp.ClientSession() as session:
                    async with session.get(self.uri) as resp:
                        if resp.status == 200:
                            self._val = await resp.read()
                        else:
                            raise BotContentError(f"async http status:{resp.status}")
            elif self.uri.startswith("file"):
                with open(self._file_uri_to_path(self.uri), "rb") as fp:
                    self._val = fp.read()
            else:
                raise BotValidateError(f"无效 uri 为：{self.uri}")
        except Exception as e:
            raise BotContentError(f"ImageContent 值加载失败，{e}")

    @property
    async def val(self) -> bytes:
        await self._load_val()
        return self._val


class AudioContent(AbstractMediaContent):
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


class VideoContent(AbstractMediaContent):
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
