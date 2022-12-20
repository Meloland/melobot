from utils.cmdInterface import ExeI
from utils.actInterface import Builder, Encoder, msg_send_packer
from utils.globalData import BOT_STORE


comment = '检查权限'
@ExeI.sync_method(alias=['权限'], userLevel=ExeI.role.USER, comment=comment,
                    paramsTip='无参数')
def auth(event: dict) -> dict:
    u_lvl = ExeI.msg_checker.get_event_lvl(event)

    if event['message_type'] == 'group':
        u_nickname = event['sender']['card']
        if u_nickname == '':
            u_nickname = event['sender']['nickname']
    elif event['message_type'] == 'private':
        u_nickname = event['sender']['nickname']

    alist = [
        u_nickname,
        BOT_STORE['custom']['BOT_NAME'],
        ExeI.msg_checker.enableSysRole(event),
        u_lvl >= ExeI.role.OWNER,
        u_lvl >= ExeI.role.SU,
        u_lvl >= ExeI.role.WHITE,
        u_lvl >= ExeI.role.USER,
    ]

    auth_str = "{} 对 {} 拥有权限：\
    \nsys：{}\nowner：{}\nsuperuser：{}\nwhite：{}\nuser：{}".format(*alist)

    action = Builder.build(
        msg_send_packer.pack(
            event,
            [Encoder.text(auth_str)],
        )
    )
    return action