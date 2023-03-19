import asyncio as aio
import random as ra
from core.Executor import EXEC, AuthRole
from common import *
from common.Action import msg_action


@EXEC.template(
    aliases=['异步测试', 'atest'], 
    userLevel=AuthRole.SU,
    comment='异步测试', 
    prompt='[测试秒数，默认为 5]'
)
async def async_test(session: BotSession, time: str='5') -> None:
    await aio.sleep(int(time))
    await session.send(f"√ {time}s 异步测试完成，标识：{ra.randint(1, 100)}")