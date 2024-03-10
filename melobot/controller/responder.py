import asyncio as aio
import traceback
from asyncio import Future

from ..types.abc import AbstractDispatcher, AbstractResponder
from ..types.exceptions import *
from ..types.typing import *

if TYPE_CHECKING:
    from ..models.event import ResponseEvent
    from ..types.abc import AbstractSender, BotAction
    from ..utils.logger import Logger


class BotResponder(AbstractResponder, AbstractDispatcher):
    """
    bot 响应模块，是 action 发送方和 bot 连接模块的媒介。
    提供 action 发送、响应回送功能
    """

    def __init__(self, logger: "Logger") -> None:
        super().__init__()
        self._resp_table: Dict[str, Future["ResponseEvent"]] = {}
        self.logger = logger

        self._ready_signal = aio.Event()
        self._action_sender: "AbstractSender"

    def bind(self, action_sender: "AbstractSender") -> None:
        """
        绑定其他核心组件的方法。独立出来，方便上层先创建实例再调用
        """
        self._action_sender = action_sender
        self._ready_signal.set()

    async def dispatch(self, resp: "ResponseEvent") -> None:
        await self._ready_signal.wait()

        try:
            if resp.id is None:
                return
            else:
                resp_fut = self._resp_table.get(resp.id)
                if resp_fut:
                    resp_fut.set_result(resp)
                    self._resp_table.pop(resp.id)
                else:
                    self.logger.error(f"收到了不匹配的携带 id 的响应：{resp.raw}")
        except aio.InvalidStateError:
            self.logger.warning(
                "等待 ResponseEvent 的异步任务已被取消，这可能意味着连接适配器响应过慢，或任务设置的超时时间太短"
            )
            self._resp_table.pop(resp.id)
        except Exception as e:
            self.logger.error(
                f"bot responder.dispatch 抛出异常：[{e.__class__.__name__}] {e}"
            )
            self.logger.debug(f"异常点的响应记录为：{resp.raw}")
            self.logger.debug("异常回溯栈：\n" + traceback.format_exc().strip("\n"))

    async def take_action(self, action: "BotAction") -> None:
        """
        响应器发送 action, 不等待响应
        """
        await self._ready_signal.wait()
        await self._action_sender.send(action)

    async def take_action_wait(self, action: "BotAction") -> Future["ResponseEvent"]:
        """
        响应器发送 action，并返回一个 Future 用于等待响应
        """
        await self._ready_signal.wait()
        fut = Future()
        self._resp_table[action.resp_id] = fut
        await self._action_sender.send(action)
        return fut
