import asyncio as aio
from asyncio import Queue
from utils.globalPattern import *
from utils.globalData import BOT_STORE
from utils.botLogger import BOT_LOGGER
from monitor import MONITOR
from handler import BotHandler
from linker import BotLinker


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
        BOT_LOGGER.debug('本次运行日志开始...')
        BOT_LOGGER.info("Qbot-MeloBot 版本：v{}, developer: {}".format(\
            BOT_STORE['kernel']['VERSION'], BOT_STORE['kernel']['DEVELOPER'])
        )
        BOT_LOGGER.info('bot 世界观形成中...  (=´ω｀=)')

        # 核心事件队列，行为队列最大长设置为事件队列的 3 倍，以适应多命令模式
        action_q = Queue(maxsize=BOT_STORE['operation']['WORK_QUEUE_LEN']*3)
        event_q = Queue(maxsize=BOT_STORE['operation']['WORK_QUEUE_LEN'])
        prior_action_q = Queue(maxsize=BOT_STORE['kernel']['PRIOR_QUEUE_LEN']*3)
        prior_event_q = Queue(maxsize=BOT_STORE['kernel']['PRIOR_QUEUE_LEN'])

        # 实例化连接对象
        bot_linker = BotLinker(action_q, event_q, prior_action_q, prior_event_q)
        coro_list = bot_linker.coro_getter()
        
        # 实例化调度对象
        bot_handler = BotHandler(action_q, event_q, prior_action_q, prior_event_q)
        coro_list.extend(bot_handler.coro_getter())

        # 交给 Monitor 管理
        MONITOR.bind(bot_linker, bot_handler)
        MONITOR.hold_coros(*coro_list)
        
        BOT_LOGGER.info('bot 意识形成完毕√')
        BOT_LOGGER.info('bot 开始觉醒!~ >w<')
        await MONITOR.run_bot()

        BOT_LOGGER.info("bot 已关闭，下次见哦~")


if __name__ == "__main__":
    the_loop = aio.new_event_loop()
    aio.set_event_loop(the_loop)
    # 键盘中断无法在协程中捕获，因此外层处理
    try:
        aio.run(MeloBot().main())
    except KeyboardInterrupt:
        BOT_LOGGER.debug("接收到键盘中断...")
    BOT_LOGGER.debug("本次运行日志结束...")

