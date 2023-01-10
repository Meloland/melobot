import traceback
import time as time
import asyncio as aio
import datetime as dt
import importlib as ipl
from common.Typing import *
from common.Global import *
from common.Action import BotAction
from common.Store import BOT_STORE
from common.Logger import BOT_LOGGER
from .Linker import BotLinker
from .Handler import BotHandler


class BotMonitor(Singleton):
    """
    Bot 监视器，管理 bot 的所有核心异步任务，
    同时负责 bot 的开启和关闭
    """
    def __init__(self) -> None:
        super().__init__()
        self.start_time = time.time()
        self.format_start_time = dt.datetime.now().strftime('%m-%d %H:%M:%S')
        self.linker = None
        self.handler = None
        self.loop = None
        self.corolist = []
        self.tasklist = []

    def get_loop(self) -> None:
        """
        获得事件循环并存储为属性
        """
        self.loop = aio.get_running_loop()

    def bind(self, linker: BotLinker, handler: BotHandler) -> None:
        """
        绑定 BotLinker 和 BotHandler 实例
        """
        self.linker = linker
        self.handler = handler

    def hold_coros(self, *coros: Coroutine) -> None:
        """
        获得来自 BotLinker 和 BotHandler 的核心异步函数（协程）
        """
        for coro in coros:
            self.corolist.append(coro)
    
    def start_tasks(self) -> None:
        """
        转化协程为任务，并立即注册到事件循环
        """
        for coro in self.corolist:
            t = aio.create_task(coro)
            self.tasklist.append(t)
        # 加入自启任务
        t = aio.create_task(self.run_startup())
        self.tasklist.append(t)

    def add_tasks(self, *coros: List[Coroutine]) -> None:
        """
        通过 Monitor 将协程注册为异步任务。
        主要用于非命令执行过程中的常驻异步任务注册，在此注册便于管理
        """
        for coro in coros:
            t = aio.create_task(coro)
            self.tasklist.append(t)

    async def close_link(self) -> None:
        """
        关闭 bot 的 ws 连接
        """
        if self.linker.ws and not self.linker.ws.closed:
            await self.linker.close()

    async def close_pool(self) -> None:
        """
        关闭 bot 用于同步任务异步化的线程池
        """
        pool = BOT_STORE['kernel']['POOL']
        pool.shutdown(wait=False)
        BOT_LOGGER.debug(f"bot 同步任务辅助线程池已关闭")

    async def run_startup(self) -> None:
        """
        载入自启任务，并执行
        """
        the_module = ipl.import_module('.Startup', __package__)
        await the_module.startup()

    async def run_bot(self) -> None:
        """
        运行 bot，并捕获处理各种运行异常
        """
        try:
            await self.linker.start()
            self.start_tasks()
            await aio.wait(
                self.tasklist, 
                timeout=BOT_STORE['operation']['WORKING_TIME']
            )
        except aio.CancelledError:
            BOT_LOGGER.debug("异步核心任务被卸载")
        except Exception as e:
            BOT_LOGGER.debug(traceback.format_exc())
            BOT_LOGGER.error(f"bot 非正常关闭，退出原因：{e}")
        finally:
            await self.close_link()
            await self.close_pool()

    async def stop_bot(self) -> None:
        """
        卸载 bot 所有异步任务。主要用于在命令模板中显式关闭 bot。
        不通过该方法关闭 bot 也可以，因为 run_bot 方法有对应的异常处理
        """
        try:
            for task in self.tasklist:
                task.cancel()
                await task
            BOT_LOGGER.info("bot 所有异步核心任务已正常卸载 awa")
        except aio.CancelledError:
            BOT_LOGGER.debug("异步核心任务被卸载")
        # 不需要额外再做关闭连接和关闭线程池的处理，因为这里的异常最后会在 run_bot 那里捕获

    @property
    def bot_start_time(self) -> str:
        return self.format_start_time

    @property
    def bot_running_time(self) -> str:
        """
        获取运行时间
        """
        def format_nums(*timeNum: List[int]) -> str:
            return [str(num) if num >= 10 else '0' + str(num) for num in timeNum]
        
        worked_time = int(time.time() - self.start_time)
        days = worked_time // 3600 // 24
        hours = worked_time // 3600 % 24
        mins = worked_time // 60 % 60
        secs = worked_time % 60
        time_str_list = format_nums(days, hours, mins, secs)
        return ":".join(time_str_list)

    async def place_action(self, action: BotAction) -> None:
        """
        通过 Monitor 暴露的此接口，直接发送 action。
        一般用于非命令执行中的行为发送
        """
        await self.linker.action_q.put(action)

    async def place_prior_action(self, action: BotAction) -> None:
        """
        通过 Monitor 暴露的此接口，直接发送 prior action。
        一般用于非命令执行中的行为发送
        """
        await self.linker.prior_action_q.put(action)


MONITOR = BotMonitor()
BOT_STORE['kernel']['MONITOR'] = MONITOR