from typing_extensions import Any, ParamSpec, TypeVar

T = TypeVar("T", default=Any)
V = TypeVar("V", default=Any)
P = ParamSpec("P", default=Any)


PROTOCOL_NAME = "Console"
PROTOCOL_VERSION = "1"
PROTOCOL_SUPPORT_AUTHOR = "Meloland"
PROTOCOL_IDENTIFIER = f"{PROTOCOL_NAME}-v{PROTOCOL_VERSION}@{PROTOCOL_SUPPORT_AUTHOR}"
