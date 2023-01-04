from utils.Interface import ExeI, AuthRole
from utils.Event import *
from utils.Action import Builder, Encoder, msg_send_packer

@ExeI.template(
    aliases=['戳'],
    userLevel=AuthRole.USER,
    comment='让 bot 戳一戳你',
    prompt='无参数'
)
def poke(event: BotEvent) -> dict:
    if event.is_msg():
        user_id = event.msg.sender.id
    elif event.is_notice():
        user_id = event.notice.operator_id
    action = Builder.build(
        msg_send_packer.pack(
            event,
            [Encoder.poke(user_id, "dict")]
        )
    )
    return action