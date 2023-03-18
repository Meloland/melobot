import time
import asyncio as aio
from .Monitor import MONITOR
from common.Utils import *
from common.Action import *


async def startup():
    """
    所有自启任务应该在此函数内部调用
    """
    await get_bot_info()
    # schedule_tasks()


async def get_bot_info() -> None:
    """
    发送获取 bot 信息的 action
    """
    action = get_login_info_action(True)
    await MONITOR.place_prior_action(action)


def schedule_tasks():
    """
    设置定时任务
    """
    def get_duration(cur_time: float, h: int=12, m: int=0, s: int=0) -> int:
        """
        获取当前时间，距离每天指定时间点的剩余时长。
        使用 24h 时间制
        """
        next_time = list(time.localtime(cur_time))[:6]
        next_time[3], next_time[4], next_time[5] = h, m, s
        next_time = time.mktime(time.strptime(":".join(map(str, next_time)), "%Y:%m:%d:%H:%M:%S"))
        return int(next_time - cur_time) if next_time >= cur_time else int(next_time + 24*3600 - cur_time)

    async def everyday_hello() -> None:
        """
        每日定时问号任务
        """
        t = get_duration(time.time(), 12, 0, 0)
        aio.sleep(t+3)
        while True:
            pass
    
    MONITOR.add_tasks(everyday_hello())
        