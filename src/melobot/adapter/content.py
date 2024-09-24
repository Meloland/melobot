from __future__ import annotations

import mimetypes
from typing import Hashable, Sequence

from typing_extensions import TypeVar


class Content: ...


ContentT = TypeVar("ContentT", bound=Content, default=Content)


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


class VoiceContent(AudioContent): ...


class VideoContent(MediaContent): ...


class FileContent(Content):
    def __init__(self, name: str, flag: Hashable) -> None:
        super().__init__()
        self.flag = flag
        self.name = name

    def __repr__(self) -> str:
        return f"[melobot File: {self.name} at {self.flag}]"


class ReferContent(Content):
    def __init__(self, prompt: str, flag: Hashable, contents: Sequence[Content]) -> None:
        super().__init__()
        self.flag = flag
        self.prompt = prompt
        self.sub_contents = contents

    def __repr__(self) -> str:
        return f"[melobot Refer: {self.prompt} at {self.flag}]"


class ResourceContent(Content):
    def __init__(self, name: str, url: str) -> None:
        super().__init__()
        self.url = url
        self.name = name

    def __repr__(self) -> str:
        return f"[melobot Resource: {self.name} at {self.url}]"
