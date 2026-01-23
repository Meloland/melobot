from os import PathLike

from typing_extensions import Sequence

from ..ctx import EventOrigin, FlowCtx
from .base import Adapter
from .content import Content, TextContent
from .model import ActionHandleGroup, Event

_CTX = FlowCtx()


async def send_text(*texts: str | TextContent) -> ActionHandleGroup:
    """通用文本输出方法"""
    return await _ctx_adapter().__send_text__(*texts)


async def send_media(
    name: str,
    raw: bytes | None = None,
    url: str | None = None,
    mimetype: str | None = None,
) -> ActionHandleGroup:
    """通用媒体内容输出方法"""
    return await _ctx_adapter().__send_media__(name, raw, url, mimetype)


async def send_image(
    name: str,
    raw: bytes | None = None,
    url: str | None = None,
    mimetype: str | None = None,
) -> ActionHandleGroup:
    """通用图像内容输出方法"""
    return await _ctx_adapter().__send_image__(name, raw, url, mimetype)


async def send_audio(
    name: str,
    raw: bytes | None = None,
    url: str | None = None,
    mimetype: str | None = None,
) -> ActionHandleGroup:
    """通用音频内容输出方法"""
    return await _ctx_adapter().__send_audio__(name, raw, url, mimetype)


async def send_voice(
    name: str,
    raw: bytes | None = None,
    url: str | None = None,
    mimetype: str | None = None,
) -> ActionHandleGroup:
    """通用语音内容输出方法"""
    return await _ctx_adapter().__send_voice__(name, raw, url, mimetype)


async def send_video(
    name: str,
    raw: bytes | None = None,
    url: str | None = None,
    mimetype: str | None = None,
) -> ActionHandleGroup:
    """通用视频内容输出方法"""
    return await _ctx_adapter().__send_video__(name, raw, url, mimetype)


async def send_file(name: str, path: str | PathLike[str]) -> ActionHandleGroup:
    """通用文件输出方法"""
    return await _ctx_adapter().__send_file__(name, path)


async def send_refer(event: Event, contents: Sequence[Content] | None = None) -> ActionHandleGroup:
    """通用过往事件引用输出方法"""
    return await _ctx_adapter().__send_refer__(event, contents)


async def send_resource(name: str, url: str) -> ActionHandleGroup:
    """通用其他资源输出方法"""
    return await _ctx_adapter().__send_resource__(name, url)


def _ctx_adapter() -> Adapter:
    event = _CTX.get_event()
    return EventOrigin.get_origin(event).adapter
