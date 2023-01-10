from core.Interface import ExeI, AuthRole
from common import *
from common.Action import msg_action


@ExeI.template(
    aliases=['权限'], 
    userLevel=AuthRole.USER, 
    comment='权限检查',
    prompt='无参数'
)
def auth(event: BotEvent) -> BotAction:
    u_lvl = ExeI.msg_checker.get_event_lvl(event)

    if event.msg.is_group():
        u_nickname = event.msg.sender.group_card
        if u_nickname == '':
            u_nickname = event.msg.sender.nickname
    elif event.msg.is_private():
        u_nickname = event.msg.sender.nickname

    alist = [
        u_nickname,
        BOT_STORE['custom']['BOT_NAME'],
        u_lvl >= AuthRole.OWNER,
        u_lvl >= AuthRole.SU,
        u_lvl >= AuthRole.WHITE,
        u_lvl >= AuthRole.USER,
    ]

    auth_str = "{} 对 {} 拥有权限：\
    \nowner：{}\nsuperuser：{}\nwhite：{}\nuser：{}".format(*alist)

    return msg_action(
        auth_str,
        event.msg.is_private(),
        event.msg.sender.id,
        event.msg.group_id,
        True
    )