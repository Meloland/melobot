from ..typ import PathLike
from .base import SrcInfoLocal
from .model import ActionHandle

_SRC_INFO_LOCAL = SrcInfoLocal()


def send_text(text: str) -> tuple[ActionHandle, ...]:
    return _SRC_INFO_LOCAL.get().adapter.send_text(text)


def send_bytes(data: bytes) -> tuple[ActionHandle, ...]:
    return _SRC_INFO_LOCAL.get().adapter.send_bytes(data)


def send_file(path: str | PathLike[str]) -> tuple[ActionHandle, ...]:
    return _SRC_INFO_LOCAL.get().adapter.send_file(path)


def send_video(
    name: str,
    uri: str | None = None,
    raw: bytes | None = None,
    mimetype: str | None = None,
) -> tuple[ActionHandle, ...]:
    return _SRC_INFO_LOCAL.get().adapter.send_video(name, uri, raw, mimetype)


def send_audio(
    name: str,
    uri: str | None = None,
    raw: bytes | None = None,
    mimetype: str | None = None,
) -> tuple[ActionHandle, ...]:
    return _SRC_INFO_LOCAL.get().adapter.send_audio(name, uri, raw, mimetype)
