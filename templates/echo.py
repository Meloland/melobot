from core.Interface import ExeI, AuthRole
from common import *
from common.Action import msg_action


@ExeI.template(
    aliases=['print', '复读'], 
    userLevel=AuthRole.USER, 
    comment='复读',
    prompt='无参数',
)
def echo(event: BotEvent, text: str) -> BotAction:
    return msg_action(
        text,
        event.msg.is_private(),
        event.msg.sender.id,
        event.msg.group_id,
        True
    )
