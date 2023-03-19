import traceback
import time as time
import asyncio as aio
import datetime as dt
import importlib as ipl
from common.Typing import *
from common.Utils import *
from common.Action import BotAction
from common.Store import *
from .Linker import BotLinker
from .Handler import BotHandler
from .Responder import BotResponder


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
        self.responder = None
        self.corolist = []
        self.tasklist = []

    def bind_kernel(self, linker: BotLinker, handler: BotHandler, responder: BotResponder) -> None:
        """
        绑定 BotLinker, BotHandler 和 BotResponder 实例
        """
        self.linker = linker
        self.handler = handler
        self.responder = responder

    def hold_coros(self, *coros: Coroutine) -> None:
        """
        获得来自 otLinker, BotHandler 和 BotResponder 的核心异步函数（协程）
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
        self.tasklist.append(aio.create_task(self.run_startup()))

    def add_rountine_tasks(self, *coros: List[Coroutine]) -> None:
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

    async def bot_dispose(self) -> None:
        """
        释放依赖的资源，包括 BOT_STORE.cmd, BOT_STORE.resources 和 BOT_STORE.plugins
        """
        await BOT_STORE.cmd.dispose_all()
        await BOT_STORE.resources.dispose_all()
        await BOT_STORE.plugins.dispose_all()

    async def run_startup(self) -> None:
        """
        载入自启任务，并执行
        """
        the_module = ipl.import_module('.Startup', __package__)
        await the_module.startup()

    async def run_kernel(self) -> None:
        """
        运行 bot 所有核心异步协程，启动 bot
        """
        try:
            await self.linker.start()
            self.start_tasks()
            await aio.wait(
                self.tasklist, 
                timeout=BOT_STORE.config.working_time
            )
        except aio.CancelledError:
            BOT_STORE.logger.debug("异步核心任务被卸载")
        except Exception as e:
            BOT_STORE.logger.debug(traceback.format_exc())
            BOT_STORE.logger.error(f"bot 非正常关闭，退出原因：{e}")
        finally:
            await self.close_link()
            await self.bot_dispose()

    async def stop_kernel(self) -> None:
        """
        卸载 bot 所有所有核心异步协程。主要用于在命令模板中显式关闭 bot。
        不通过该方法关闭 bot 也可以，因为 run_kernel 方法有对应的异常处理。
        注：该方法的异常将会传递到 run_kernel 中
        """
        try:
            for task in self.tasklist:
                task.cancel()
                await task
            BOT_STORE.logger.info("bot 所有异步核心任务已正常卸载 awa")
        except aio.CancelledError:
            BOT_STORE.logger.debug("异步核心任务被卸载")
        # 不需要额外再做关闭连接和关闭线程池的处理，因为这里的异常最后会在 run_kernel 那里捕获

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


MONITOR = BotMonitor()
BOT_STORE.monitor = MONITOR