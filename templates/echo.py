from utils.cmdInterface import ExeI
from utils.actInterface import Builder, Encoder, msg_send_packer


@ExeI.template(
    aliases=['print', '复读'], 
    userLevel=ExeI.role.USER, 
    comment='复读',
    prompt='无参数'
)
def echo(event: dict, text: str) -> dict:
    action = Builder.build(
        msg_send_packer.pack(
            event,
            [Encoder.text(text)],
        )
    )
    return action