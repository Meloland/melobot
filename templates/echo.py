from utils.Interface import ExeI, AuthRole
from utils.Definition import *
from utils.Event import *
from utils.Action import msg_action, BotAction


@ExeI.template(
    aliases=['print', '复读'], 
    userLevel=AuthRole.USER, 
    comment='复读',
    prompt='无参数'
)
def echo(event: BotEvent, text: str) -> BotAction:
    return msg_action(
        text,
        event.msg.is_private(),
        event.msg.sender.id,
        event.msg.group_id,
        True
    )