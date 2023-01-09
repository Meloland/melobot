import asyncio as aio
import random as ra
from utils.Interface import ExeI, AuthRole
from utils.Event import *
from utils.Action import msg_action, BotAction


@ExeI.template(
    aliases=['异步测试', 'atest'], 
    userLevel=AuthRole.SU, 
    comment='异步测试', 
    prompt='[测试秒数，默认为 5]'
)
async def async_test(event: BotEvent, time: str='5') -> BotAction:
    await aio.sleep(int(time))
    return msg_action(
        f"√ {time}s 异步测试完成，标识：{ra.randint(1, 100)}",
        event.msg.is_private(),
        event.msg.sender.id,
        event.msg.group_id,
        True
    )