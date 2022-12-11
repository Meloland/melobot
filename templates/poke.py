from utils.cmdInterface import ExeI
from utils.actInterface import Builder, Encoder, msg_send_packer
from utils.globalData import BOT_STORE


comment = '让{}戳一戳你'.format(BOT_STORE['custom']['BOT_NAME'])
@ExeI.sync_method(alias=['戳'], userLevel=ExeI.role.USER, comment=comment, 
                    paramsTip='无参数')
def poke(event: dict) -> dict:
    action = Builder.build(
        msg_send_packer.pack(
            event,
            [Encoder.poke(event['user_id'], "dict")]
        )
    )
    return action