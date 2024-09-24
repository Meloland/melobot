from os import PathLike
from typing import Sequence

from ..adapter.content import Content
from ..adapter.model import ActionHandle, Event
from ..ctx import EventBuildInfoCtx

_CTX = EventBuildInfoCtx()


async def send_text(text: str) -> tuple[ActionHandle, ...]:
    return await _CTX.get().adapter.send_text(text)


async def send_media(
    name: str,
    raw: bytes | None = None,
    url: str | None = None,
    mimetype: str | None = None,
) -> tuple[ActionHandle, ...]:
    return await _CTX.get().adapter.send_media(name, raw, url, mimetype)


async def send_image(
    name: str,
    raw: bytes | None = None,
    url: str | None = None,
    mimetype: str | None = None,
) -> tuple[ActionHandle, ...]:
    return await _CTX.get().adapter.send_image(name, raw, url, mimetype)


async def send_audio(
    name: str,
    raw: bytes | None = None,
    url: str | None = None,
    mimetype: str | None = None,
) -> tuple[ActionHandle, ...]:
    return await _CTX.get().adapter.send_audio(name, raw, url, mimetype)


async def send_voice(
    name: str,
    raw: bytes | None = None,
    url: str | None = None,
    mimetype: str | None = None,
) -> tuple[ActionHandle, ...]:
    return await _CTX.get().adapter.send_voice(name, raw, url, mimetype)


async def send_video(
    name: str,
    raw: bytes | None = None,
    url: str | None = None,
    mimetype: str | None = None,
) -> tuple[ActionHandle, ...]:
    return await _CTX.get().adapter.send_video(name, raw, url, mimetype)


async def send_file(name: str, path: str | PathLike[str]) -> tuple[ActionHandle, ...]:
    return await _CTX.get().adapter.send_file(name, path)


async def send_refer(
    event: Event, contents: Sequence[Content] | None = None
) -> tuple[ActionHandle, ...]:
    return await _CTX.get().adapter.send_refer(event, contents)


async def send_resource(name: str, url: str) -> tuple[ActionHandle, ...]:
    return await _CTX.get().adapter.send_resource(name, url)
