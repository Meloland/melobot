import sys
import os

os.chdir('../bot')
sys.path.append('../bot')
sys.path.append('..')

import sys
import asyncio as aio
from asyncio import Queue
from bot.common.Store import BOT_STORE
from bot.common.Exceptions import *
from bot.core.Linker import BotLinker
from bot.core.Handler import BotHandler
from bot.core.Responder import BotResponder
from bot.core.Monitor import MONITOR
# 禁用所有日志输出，避免刷屏干扰
BOT_STORE.logger.info = lambda x: None
BOT_STORE.logger.debug = lambda x: None
BOT_STORE.logger.error = lambda x: None
BOT_STORE.logger.warn = lambda x: None
BOT_STORE.logger.warning = lambda x: None
BOT_STORE.logger.critical = lambda x: None


class MeloBot:
    async def main(self) -> None:
        action_q = Queue(maxsize=BOT_STORE.config.work_queue_len*3)
        event_q = Queue(maxsize=BOT_STORE.config.work_queue_len)
        prior_action_q = Queue(maxsize=BOT_STORE.meta.prior_queue_len*3)
        prior_event_q = Queue(maxsize=BOT_STORE.meta.prior_queue_len)
        resp_q = Queue(maxsize=BOT_STORE.config.work_queue_len*3)

        bot_linker = BotLinker(action_q, event_q, prior_action_q, prior_event_q)
        kernel_coros = bot_linker.coro_getter()
        bot_handler = BotHandler(event_q, prior_event_q, resp_q)
        kernel_coros.extend(bot_handler.coro_getter())
        bot_responder = BotResponder(action_q, prior_action_q, resp_q)
        kernel_coros.extend(bot_responder.coro_getter())

        MONITOR.bind_kernel(bot_linker, bot_handler, bot_responder)
        MONITOR.hold_coros(*kernel_coros)
        await MONITOR.run_kernel()


if __name__ == "__main__":
    the_loop = aio.new_event_loop()
    aio.set_event_loop(the_loop)
    try:
        aio.run(MeloBot().main())
    except KeyboardInterrupt:
        pass
