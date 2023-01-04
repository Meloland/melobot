import asyncio as aio
import random as ra
from utils.cmdInterface import ExeI, AuthRole
from utils.botEvent import *
from utils.botAction import Builder, Encoder, msg_send_packer


@ExeI.template(
    aliases=['异步测试', 'atest'], 
    userLevel=AuthRole.SU, 
    comment='异步测试', 
    prompt='[测试秒数，默认为 5]'
)
async def async_test(event: BotEvent, time: str='5') -> dict:
    await aio.sleep(int(time))
    action = Builder.build(
        msg_send_packer.pack(
            event,
            [Encoder.text(f"√ {time}s 异步测试完成，标识：{ra.randint(1, 100)}")],
        )
    )
    return action