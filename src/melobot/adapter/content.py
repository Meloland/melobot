from __future__ import annotations

import mimetypes
from typing import Hashable, Sequence

from ..typ import TypeVar


class Content: ...


ContentT = TypeVar("ContentT", bound=Content)


class TextContent(Content):
    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text


class MediaContent(Content):
    def __init__(
        self,
        *,
        name: str,
        url: str | None = None,
        raw: bytes | None = None,
        mimetype: str | None = None,
    ) -> None:
        super().__init__()
        self.name = name
        self.url = url
        self.val = raw if raw is not None else None
        if mimetype is None:
            self.mimetype, _ = mimetypes.guess_type(self.name)


class ImageContent(MediaContent): ...


class AudioContent(MediaContent): ...


class VoiceContent(MediaContent): ...


class VideoContent(MediaContent): ...


class FileContent(Content):
    def __init__(self, name: str, flag: Hashable) -> None:
        super().__init__()
        self.scope = flag
        self.name = name if name else f"[File: {flag}]"


class ReferContent(Content):
    def __init__(self, prompt: str, flag: Hashable, contents: Sequence[Content]) -> None:
        super().__init__()
        self.flag = flag
        self.prompt = prompt if prompt else f"[Refer: {flag}]"
        self.sub_contents = contents


class ResourceContent(Content):
    def __init__(self, name: str, url: str) -> None:
        super().__init__()
        self.url = url
        self.name = name if name else f"[Share: {url}]"
