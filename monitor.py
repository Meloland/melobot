import asyncio as aio
import traceback
import time as t
import datetime as dt
import websockets.exceptions as wse
from typing import Coroutine
from utils.globalPattern import *
from utils.globalData import BOT_STORE
from utils.botLogger import BOT_LOGGER


class BotMonitor(Singleton):
    """
    Bot 监视器，管理 bot 的所有核心异步任务，
    同时负责 bot 的开启和关闭
    """
    def __init__(self) -> None:
        super().__init__()
        self.start_time = t.time()
        self.format_start_time = dt.datetime.now().strftime('%m-%d %H:%M:%S')
        self.linker = None
        self.handler = None
        self.corolist = []
        self.tasklist = []

    def bind(self, linker, handler) -> None:
        """
        绑定 BotLinker 和 BotHandler 实例
        """
        self.linker = linker
        self.handler = handler

    def hold_coros(self, *coroList: Coroutine) -> None:
        """
        获得来自 BotLinker 和 BotHandler 的核心异步函数（协程）
        """
        for coro in coroList:
            self.corolist.append(coro)
    
    def start_tasks(self) -> None:
        """
        转化协程为任务，并立即注册到事件循环
        """
        for coro in self.corolist:
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
        卸载 bot 所有核心异步任务。主要用于在命令模板中显式关闭 bot。
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
        worked_time = t.time() - self.start_time
        return t.strftime("%H:%M:%S", t.gmtime(worked_time))


MONITOR = BotMonitor()
BOT_STORE['kernel']['MONITOR'] = MONITOR