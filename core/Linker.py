import sys
import websockets
import traceback
import asyncio as aio
import websockets.exceptions as wse
from asyncio import Queue
from components import Parser
from components import Access
from common.Typing import *
from common.Global import *
from common.Event import BotEvent, KernelEvent
from common.Action import BotAction
from common.Store import BOT_STORE
from common.Logger import BOT_LOGGER


class BotLinker(Singleton):
    """
    Bot 连接模块。
    负责与 cq 建立连接，并将接收到的事件装入事件队列。
    同时监控行为队列，及时将内部产生的行为发送给 cq 处理
    """
    def __init__(self, action_queue: Queue, event_queue: Queue, \
                prior_action_queue: Queue, prior_event_queue: Queue) -> None:
        super().__init__()
        host, port = BOT_STORE['operation']['CONNECT_HOST'], \
                    BOT_STORE['operation']['CONNECT_PORT']
        self.url = f'ws://{host}:{port}'
        self.ws = None

        self.action_q = action_queue
        self.event_q = event_queue
        self.prior_action_q = prior_action_queue
        self.prior_event_q = prior_event_queue

        self.prior_filter = PriorEventFilter()

    async def start(self) -> None:
        """
        打开连接
        """
        self.ws = await websockets.connect(self.url)
        await self.ws.recv()
        BOT_LOGGER.info('与 cq 成功建立 websocket 连接')

    async def close(self) -> None:
        """
        关闭连接
        """
        await self.ws.close()
        BOT_LOGGER.info('与 cq 的连接已正常关闭')

    async def __aenter__(self) -> object:
        await self.start()
        return self

    async def __aexit__(self, exc_type:Exception, exc_val:str, exc_tb:traceback) -> None:
        await self.close()

    async def get_action(self) -> None:
        """
        监控 action 队列，并指派给 cq
        """
        try:
            while True:
                try:
                    action: BotAction = await self.action_q.get()
                    astr = action.flatten()
                    await self.ws.send(astr)
                    await aio.sleep(BOT_STORE['operation']['COOLDOWN_TIME'])
                except Exception as e:
                    BOT_LOGGER.debug(traceback.format_exc())
                    BOT_LOGGER.error(f'内部发生预期外的异常：{e}')
        except aio.CancelledError:
            BOT_LOGGER.debug('linker.get_action 已被卸载')
        except wse.ConnectionClosedOK:
            pass

    async def put_event(self) -> None:
        """
        监控 cq 上报，并放入 event 队列，若有优先 event，
        移交给 put_prior_event 处理
        """
        try:
            while True:
                try:
                    raw_e = await self.ws.recv()
                    # 有时 go-cqhttp 会因为无法解析特殊字符问题，导致返回消息为空，这里需要做一次判断
                    if raw_e == "": continue
                    event = BotEvent(raw_e)

                    # 如果识别到优先事件，分拣处理
                    if self.prior_filter.is_prior(event): 
                        try:
                            BOT_LOGGER.debug('识别到优先事件')
                            t = aio.create_task(self.put_prior_event(event))
                            await aio.wait_for(t, timeout=BOT_STORE['kernel']['KERNEL_TIMEOUT'])
                            BOT_LOGGER.debug('优先事件已成功放置~')
                        except aio.TimeoutError:
                            pass
                        finally:
                            continue
                    
                    # 若队满，再生成一个队满事件，作为优先事件塞入优先队列，方便处理模块立即响应
                    # 同时立即完成循环，取消本次事件
                    if self.event_q.full():
                        try:
                            BOT_LOGGER.debug('队满响应机制已触发，生成队满响应事件并尝试放置中...')
                            ke = KernelEvent('eq_full', originEvent=event)
                            t = aio.create_task(self.put_prior_event(ke))
                            await aio.wait_for(t, timeout=BOT_STORE['kernel']['KERNEL_TIMEOUT'])
                            BOT_LOGGER.debug('队满响应事件已成功放置~')
                        except aio.TimeoutError:
                            pass
                        BOT_LOGGER.warning('事件队列已满！短时间内可能无法响应事件')
                        continue

                    # 常规事件处理
                    await self.event_q.put(event)
                # 下面有 Exception 捕获，不方便直接传递异常到 monitor，直接终止
                except wse.ConnectionClosedError:
                    BOT_LOGGER.warning('cq 主动关闭连接，bot 清理资源后将自动关闭')
                    # 直接抛出终止信号，随后会自动交由 monitor.run_bot 处理
                    sys.exit(0)
                except Exception as e:
                    BOT_LOGGER.debug(traceback.format_exc())
                    BOT_LOGGER.error(f'linker 内部发生预期外的异常：{e}，事件对象为：{event}')
        except aio.CancelledError:
            BOT_LOGGER.debug('linker.put_event 已被卸载')
        except wse.ConnectionClosedOK:
            pass

    async def get_prior_action(self) -> None:
        """
        监控优先 action 队列，并立即指派给 cq
        """
        try:
            while True:
                try:
                    action: BotAction = await self.prior_action_q.get()
                    astr = action.flatten()
                    await self.ws.send(astr)
                    await aio.sleep(BOT_STORE['operation']['COOLDOWN_TIME'])
                except Exception as e:
                    BOT_LOGGER.debug(traceback.format_exc())
                    BOT_LOGGER.error(f'内部发生预期外的异常：{e}')
        except aio.CancelledError:
            BOT_LOGGER.debug('linker.get_prior_action 已被卸载')
        except wse.ConnectionClosedOK:
            pass

    async def put_prior_event(self, event: BotEvent) -> None:
        """
        获得来自 put_event 的优先 event，并立即放入优先 event 队列
        """
        try:
            # 如果优先队列也满了，那就等待，外部有超时控制
            if self.prior_event_q.full():
                BOT_LOGGER.warning('优先事件队列已满！短时间内可能无法响应更多优先事件')
            await self.prior_event_q.put(event)
        except aio.CancelledError:
            BOT_LOGGER.debug('优先事件放置因超时被取消')
    
    def coro_getter(self) -> List[Coroutine]:
        """
        返回 linker 所有核心的异步协程给主模块
        """
        return [
            self.put_event(),
            self.get_prior_action(),
            self.get_action()
        ]


class PriorEventFilter(Singleton):
    """
    优先事件分拣器
    """
    def __init__(self) -> None:
        pass

    def is_prior(self, event: BotEvent) -> bool:
        # 优先事件判断，但不对事件进行修改，事件将由 handler 模块转交给 eventExec 模块负责
        # 判断流程：是否是消息 > 文本消息是否为空 > 是否具有 owner 权限 > 是否是优先消息
        if event.is_msg() and event.msg.text != '' and Access.MSG_CHECKER.check(Access.SU, event):
            return Parser.EC_PARSER.prior_check(event.msg.text)


if __name__ == "__main__":
    pass