from utils.botAction import Builder, Encoder, msg_send_packer


def echo(event: dict, text: str) -> dict:
    """
    系统内部专用回显指令，用于发出提示消息等功能。
    独立于用户级 echo 调用，实现权限分离
    """
    action = Builder.build(
        msg_send_packer.pack(
            event,
            [Encoder.text(text)],
        )
    )
    return action