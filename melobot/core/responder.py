import asyncio as aio
from asyncio import Future

from ..interface.core import IActionResponder, IActionSender, IRespDispatcher
from ..interface.typing import *
from ..models.action import BotAction
from ..models.event import RespEvent
from ..models.exceptions import *


class BotResponder(IActionResponder, IRespDispatcher):
    """
    bot 响应模块，是 action 发送方和 bot 连接模块的媒介。
    提供 action 发送、响应回送功能
    """
    def __init__(self) -> None:
        super().__init__()
        self.resp_table: Dict[str, Future[RespEvent]] = {}

        self._ready_signal = aio.Event()
        self.action_sender: IActionSender

    def bind(self, action_sender: IActionSender) -> None:
        """
        绑定其他核心组件的方法。独立出来，方便上层先创建实例再调用
        """
        self.action_sender = action_sender
        self._ready_signal.set()

    async def dispatch(self, resp: RespEvent) -> None:
        await self._ready_signal.wait()

        if resp.id is None:
            return
        else:
            resp_fut = self.resp_table.get(resp.id)
            if resp_fut:
                resp_fut.set_result(resp)
                self.resp_table.pop(resp.id)
            else:
                raise BotUnexceptedObj(f"收到了不匹配的携带 id 的响应：{resp.raw}")

    async def take_action(self, action: BotAction) -> None:
        """
        响应器发送 action, 不等待响应
        """
        await self._ready_signal.wait()
        await self.action_sender.send(action)
    
    async def take_action_wait(self, action: BotAction) -> Future[RespEvent]:
        """
        响应器发送 action，并返回一个 Future 用于等待响应
        """
        await self._ready_signal.wait()

        fut = Future()
        self.resp_table[action.resp_id] = fut
        await self.action_sender.send(action)
        return fut
