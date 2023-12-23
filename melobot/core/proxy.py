import asyncio as aio

from ..interface.typing import *
from ..utils.config import BotConfig


class BotProxy:
    """
    暴露给外部使用的 BotProxy 代理对象
    """
    def __init__(self) -> None:
        self.config: BotConfig
        self._initd: aio.Task

    def _bind(self, config: BotConfig, work: aio.Task) -> None:
        self.config = config
        self._initd = work


BOT_PROXY = BotProxy()
