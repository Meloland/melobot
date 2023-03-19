import sys
sys.path.append('.')
import asyncio as aio
from asyncio import Queue
from common.Utils import *
from common.Store import BOT_STORE
from common.Exceptions import *


BOT_STORE.logger.debug('本次运行日志开始...')
BOT_STORE.logger.info("Qbot-MeloBot 版本：v{}, developer: {}".format(
    BOT_STORE.meta.version, BOT_STORE.meta.developer
))
BOT_STORE.logger.info('bot 世界观形成中...  (=´ω｀=)')


from core.Linker import BotLinker
from core.Handler import BotHandler
from core.Responder import BotResponder
from core.Monitor import MONITOR


class MeloBot(Singleton):
    """
    bot 单例类，负责启动和管理所有子模块 ow<
    """
    def __init__(self) -> None:
        super().__init__()

    async def main(self) -> None:
        """
        装载 bot 核心实例与异步核心任务至 Monitor，并交由 Monitor 启动和管理
        """
        # 核心事件和行为队列，行为队列最大长设置为事件队列的 3 倍，以适应多命令模式
        action_q = Queue(maxsize=BOT_STORE.config.work_queue_len*3)
        event_q = Queue(maxsize=BOT_STORE.config.work_queue_len)
        prior_action_q = Queue(maxsize=BOT_STORE.meta.prior_queue_len*3)
        prior_event_q = Queue(maxsize=BOT_STORE.meta.prior_queue_len)
        # 响应队列，用于存储 action 发送后 cq 返回的响应事件，以在调度器和响应器间传送响应事件
        resp_q = Queue(maxsize=BOT_STORE.config.work_queue_len*3)

        # 实例化连接器对象
        bot_linker = BotLinker(action_q, event_q, prior_action_q, prior_event_q)
        kernel_coros = bot_linker.coro_getter()
        
        # 实例化调度器对象
        bot_handler = BotHandler(event_q, prior_event_q, resp_q)
        kernel_coros.extend(bot_handler.coro_getter())

        # 实例化响应器对象
        bot_responder = BotResponder(action_q, prior_action_q, resp_q)
        kernel_coros.extend(bot_responder.coro_getter())

        # 交给 Monitor 管理
        MONITOR.bind_kernel(bot_linker, bot_handler, bot_responder)
        MONITOR.hold_coros(*kernel_coros)
        
        BOT_STORE.logger.info('bot 意识形成完毕√')
        BOT_STORE.logger.info('bot 开始觉醒!~ >w<')
        await MONITOR.run_kernel()

        BOT_STORE.logger.info("bot 已关闭，下次见哦~")


if __name__ == "__main__":
    the_loop = aio.new_event_loop()
    aio.set_event_loop(the_loop)
    # 键盘中断无法在协程中捕获，因此外层处理
    try:
        aio.run(MeloBot().main())
    except KeyboardInterrupt:
        BOT_STORE.logger.debug("接收到键盘中断...")
    BOT_STORE.logger.debug("本次运行日志结束...")
