from utils.cmdInterface import ExeI
from utils.actInterface import Builder, Encoder, msg_send_packer


comment = '随机图'
@ExeI.sync_method(alias=['随机图'], userLevel=ExeI.role.USER, comment=comment, 
                    paramsTip='无参数')
def rand_image(event: dict) -> dict:
    action = Builder.build(
        msg_send_packer.pack(
            event,
            [Encoder.image(
                file='https://api.ixiaowai.cn/api/api.php',
                cache='0'
            )],
        )
    )
    return action