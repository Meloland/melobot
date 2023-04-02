from common.Typing import *
from common.Store import BOT_STORE
from common.Event import *
from common.Action import BotAction
import asyncio as aio
from asyncio import Queue, Future


class BotResponder:
    """
    bot 响应器。
    负责 action 的发送和对应 resp 的分发
    """
    def __init__(self, action_queue: Queue, prior_action_queue: Queue, resp_queue: Queue) -> None:
        self.prior_action_q = prior_action_queue
        self.action_q = action_queue
        self.resp_queue = resp_queue
        self.resp_tables: Dict[str, Future] = {}

    async def recv_and_set_resp(self) -> None:
        """
        接受 resp 对象。如果存在 id，则查 resp 表设置 future 结果
        """
        try:
            while True:
                resp_event: RespEvent = await self.resp_queue.get()
                if resp_event.resp.id is None:
                    continue
                else:
                    resp_fut = self.resp_tables.get(resp_event.resp.id)
                    if resp_fut is not None:
                        resp_fut.set_result(resp_event)
                        self.resp_tables.pop(resp_event.resp.id)
                    else:
                        BOT_STORE.logger.debug(f"不匹配的响应事件: {resp_event.raw}")
                        BOT_STORE.logger.warning("收到不匹配的响应事件！已经记录并跳过...")
        except aio.CancelledError:
            BOT_STORE.logger.debug("responder.recv_resp 已被卸载")

    async def _send_prior_action(self, prior_action: BotAction) -> None:
        """
        放置指定的优先 action 到 优先 action 队列
        """
        if self.prior_action_q.full():
            BOT_STORE.logger.warning("优先行为队列已满！短时间内可能无法产生优先行为")
        await self.prior_action_q.put(prior_action)

    async def _send_action(self, action: BotAction) -> None:
        """
        放置指定的 action 到 action 队列
        """
        if self.action_q.full():
            BOT_STORE.logger.warning("行为队列已满！短时间可能无法对任务回应")
        await self.action_q.put(action)

    async def throw_action(self, action: BotAction, isPrior: bool=False) -> None:
        """
        响应器发送 action 或 prior_action，不等待响应
        """
        if not isPrior: 
            try:
                t = aio.create_task(self._send_action(action))
                await aio.wait_for(t, timeout=BOT_STORE.meta.kernel_timeout)
            except aio.CancelledError:
                BOT_STORE.logger.debug('行为放置因超时而被取消')
                return
        else: 
            try:
                t = aio.create_task(self._send_prior_action(action))
                await aio.wait_for(t, timeout=BOT_STORE.meta.kernel_timeout)
            except aio.CancelledError:
                BOT_STORE.logger.debug('优先行为放置因超时而被取消')
                return

        # 记录
        if not (action.type.endswith('msg') and action.type.startswith('send')):
            BOT_STORE.logger.info(f"成功响应 {action.type} 事件√")

    async def wait_action(self, action: BotAction, isPrior: bool=False) -> Future:
        """
        响应器发送 action，并记录在 resp 表中，返回一个关联的 Future 给调用方
        """
        fut = Future()
        self.resp_tables[action.respId] = fut
        await self.throw_action(action, isPrior)
        return fut

    def coro_getter(self) -> List[Coroutine]:
        """
        返回 Responder 的所有核心异步协程
        """
        return [
            self.recv_and_set_resp()
        ]