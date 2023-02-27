from core.Interface import ExeI, AuthRole
from common import *
from common.Action import msg_action, poke_msg

@ExeI.template(
    aliases=['戳'],
    userLevel=AuthRole.USER,
    comment='让 bot 戳一戳你',
    prompt='无参数'
)
def poke(event: BotEvent) -> BotAction:
    if event.is_msg():
        user_id = event.msg.sender.id
        return msg_action(
            poke_msg(user_id),
            event.msg.is_private(),
            user_id,
            event.msg.group_id,
            True
        )
    elif event.is_notice():
        user_id = event.notice.operator_id
        if hasattr(event.notice, 'group_id'):
            group_id = event.notice.group_id
            isPrivate = False
        else:
            group_id = None
            isPrivate = True
        return msg_action(
            poke_msg(user_id),
            isPrivate,
            user_id,
            group_id,
            True
        )
    