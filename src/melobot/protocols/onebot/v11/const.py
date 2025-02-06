from typing_extensions import Any, ParamSpec, TypeVar

T = TypeVar("T", default=Any)
V = TypeVar("V", default=Any)
P = ParamSpec("P", default=Any)


PROTOCOL_NAME = "OneBot"
PROTOCOL_VERSION = "11"
PROTOCOL_SUPPORT_AUTHOR = "Meloland"
PROTOCOL_IDENTIFIER = f"{PROTOCOL_NAME}-v{PROTOCOL_VERSION}@{PROTOCOL_SUPPORT_AUTHOR}"

ACTION_TYPE_KEY_NAME = "action_type"
