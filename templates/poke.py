from core.Executor import EXEC, AuthRole
from common import *
from common.Action import poke_msg

@EXEC.template(
    aliases=['戳'],
    userLevel=AuthRole.USER,
    comment='让 bot 戳一戳你',
    prompt='无参数'
)
async def poke(session: BotSession) -> None:
    event = session.event
    
    if event.is_msg():
        user_id = event.msg.sender.id
        await session.custom_send(
            poke_msg(user_id),
            event.msg.is_private(),
            user_id,
            event.msg.group_id,
        )
    elif event.is_notice():
        user_id = event.notice.operator_id
        if hasattr(event.notice, 'group_id'):
            group_id = event.notice.group_id
            isPrivate = False
        else:
            group_id = None
            isPrivate = True
        await session.custom_send(
            poke_msg(user_id),
            isPrivate,
            user_id,
            group_id,
        )