from ..types.typing import TYPE_CHECKING
from .action import *
from .session import BOT_LOCAL as thisbot
from .session import (
    AttrSessionRule,
    any_event,
    get_store,
    meta_event,
    msg_args,
    msg_event,
    msg_text,
    notice_event,
    pause,
    req_evnt,
)

if TYPE_CHECKING:
    from ..bot.init import MeloBot
thisbot: "MeloBot"  # type: ignore
