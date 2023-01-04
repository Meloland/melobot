from utils.cmdInterface import ExeI, AuthRole
from utils.botEvent import *
from utils.botAction import Builder, Encoder, msg_send_packer


@ExeI.template(
    aliases=['print', '复读'], 
    userLevel=AuthRole.USER, 
    comment='复读',
    prompt='无参数'
)
def echo(event: BotEvent, text: str) -> dict:
    action = Builder.build(
        msg_send_packer.pack(
            event,
            [Encoder.text(text)],
        )
    )
    return action