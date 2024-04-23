import asyncio
from asyncio import Future

from ..base.typing import TYPE_CHECKING, cast
from ..context.session import ActionResponse
from ..utils.logger import log_exc, log_obj

if TYPE_CHECKING:
    from ..base.abc import AbstractConnector, BaseLogger, BotAction


class BotResponder:
    """Bot 响应模块，是 action 发送方和 bot 连接模块的媒介。 提供 action 发送、响应回送功能"""

    def __init__(self) -> None:
        super().__init__()
        self._resp_table: dict[str, Future[ActionResponse]] = {}
        self.logger: "BaseLogger"
        self._action_sender: "AbstractConnector"

        self._ready_signal = asyncio.Event()

    def _bind(self, logger: "BaseLogger", connector: "AbstractConnector") -> None:
        self.logger = logger
        self._action_sender = connector

    def _set_ready(self) -> None:
        self._ready_signal.set()

    async def respond(self, resp: ActionResponse) -> None:
        await self._ready_signal.wait()

        try:
            if self.logger.check_level_flag("DEBUG"):
                log_obj(self.logger.debug, resp.raw, f"收到 resp {resp:hexid}")
            if resp.id is None:
                return
            else:
                resp_fut = self._resp_table.get(resp.id)
                if resp_fut:
                    resp_fut.set_result(resp)
                    self._resp_table.pop(resp.id)
                else:
                    self.logger.error(f"收到了不匹配的携带 id 的响应：{resp.raw}")
        except asyncio.InvalidStateError:
            self.logger.warning(
                "等待响应的异步任务已被取消，这可能意味着连接器响应过慢，或任务设置的超时时间太短"
            )
            self._resp_table.pop(cast(str, resp.id))
        except Exception as e:
            self.logger.error("bot responder.dispatch 抛出异常")
            log_obj(self.logger.error, resp, "异常点 resp_event")
            log_exc(self.logger, locals(), e)

    async def take_action(self, action: "BotAction") -> None:
        """响应器发送 action, 不等待完成"""
        await self._ready_signal.wait()
        await self._action_sender._send(action)
        return None

    async def take_action_wait(self, action: "BotAction") -> Future[ActionResponse]:
        """响应器发送 action，并返回一个 Future 用于等待完成"""
        await self._ready_signal.wait()
        fut: Future[ActionResponse] = Future()
        self._resp_table[cast(str, action.resp_id)] = fut
        await self._action_sender._send(action)
        return fut
