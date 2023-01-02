from utils.actInterface import Builder, Encoder, msg_send_packer


def poke(event: dict) -> dict:
    action = Builder.build(
        msg_send_packer.pack(
            event,
            [Encoder.poke(event['user_id'], "dict")]
        )
    )
    return action