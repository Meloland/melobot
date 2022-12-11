import asyncio as aio
import random as ra
from utils.cmdInterface import ExeI
from utils.actInterface import Builder, Encoder, msg_send_packer


comment = '异步测试'
@ExeI.async_method(alias=['异步测试', 'atest'], userLevel=ExeI.role.OWNER, comment=comment,
                    paramsTip='[测试秒数，默认为 5]')
async def async_test(event: dict, time: str='5') -> dict:
    await aio.sleep(int(time))
    action = Builder.build(
        msg_send_packer.pack(
            event,
            [Encoder.text(f"√ {time}s 异步测试完成，标识：{ra.randint(1, 100)}")],
        )
    )
    return action