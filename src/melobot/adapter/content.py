from __future__ import annotations

import mimetypes
from typing import Hashable, Sequence

from typing_extensions import TypeVar


class Content:
    """通用内容基类"""


ContentT = TypeVar("ContentT", bound=Content, default=Content)


class TextContent(Content):
    """文本内容"""

    def __init__(self, text: str) -> None:
        """初始化文本内容

        :param text: 文本
        """
        super().__init__()
        self.text = text


class MediaContent(Content):
    """多媒体内容"""

    def __init__(
        self,
        *,
        name: str,
        url: str | None = None,
        raw: bytes | None = None,
        mimetype: str | None = None,
    ) -> None:
        """初始化多媒体内容

        :param name: 多媒体内容的名称
        :param raw: 多媒体内容的二进制内容
        :param url: 多媒体内容的网络地址（和 `raw` 参数二选一）
        :param mimetype: 多媒体内容的 mimetype，为空则根据 `name` 自动检测
        """
        super().__init__()
        self.name = name
        self.url = url
        self.val = raw if raw is not None else None
        if mimetype is None:
            self.mimetype, _ = mimetypes.guess_type(self.name)


class ImageContent(MediaContent):
    """图像内容，初始化方法参考基类"""


class AudioContent(MediaContent):
    """音频内容，初始化方法参考基类"""


class VoiceContent(AudioContent):
    """语音内容，初始化方法参考基类"""


class VideoContent(MediaContent):
    """视频内容，初始化方法参考基类"""


class FileContent(Content):
    """文件内容"""

    def __init__(self, name: str, flag: Hashable) -> None:
        """初始化文件内容

        :param name: 文件名
        :param flag: 文件的唯一标记
        """
        super().__init__()
        self.flag = flag
        self.name = name

    def __repr__(self) -> str:
        return f"[melobot File: {self.name} at {self.flag}]"


class ReferContent(Content):
    """引用内容"""

    def __init__(self, prompt: str, flag: Hashable, contents: Sequence[Content]) -> None:
        """初始化引用内容

        :param prompt: 引用的文本提示
        :param flag: 引用的唯一标记
        :param contents: 附加的通用内容序列
        """
        super().__init__()
        self.flag = flag
        self.prompt = prompt
        self.sub_contents = contents

    def __repr__(self) -> str:
        return f"[melobot Refer: {self.prompt} at {self.flag}]"


class ResourceContent(Content):
    """资源内容"""

    def __init__(self, name: str, url: str) -> None:
        """初始化资源内容

        :param name: 名称
        :param url: 网络地址
        """
        super().__init__()
        self.url = url
        self.name = name

    def __repr__(self) -> str:
        return f"[melobot Resource: {self.name} at {self.url}]"
