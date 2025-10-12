from __future__ import annotations

import asyncio
import contextvars
from asyncio import Queue, Task
from collections import deque

from typing_extensions import TYPE_CHECKING

from .._run import is_async_running, register_loop_started_hook
from ..adapter.base import Event
from ..handle.base import Flow
from ..log.base import LogLevel
from ..log.reflect import logger

if TYPE_CHECKING:
    from .base import Bot


class Dispatcher:
    HANDLED_FLOWS_FLAG = "HANDLED_FLOWS"
    DISPATCHED_FLAG = "DISPATCHED"

    def __init__(self) -> None:
        self.first_chan: EventChannel | None = None
        self._channel_ctx = contextvars.Context()

    def __repr__(self) -> str:
        counts: dict[int, str] = {}
        chan = self.first_chan
        while chan is not None:
            counts[chan.priority] = f"[flows:{len(chan.flow_que)}, events:{chan.event_que.qsize()}]"
            chan = chan.next
        return f"{self.__class__.__name__}({counts})"

    def set_channel_ctx(self, ctx: contextvars.Context) -> None:
        self._channel_ctx = ctx

    def add(self, *flows: Flow) -> None:
        for f in flows:
            lvl = f.priority

            if self.first_chan is None:
                self.first_chan = EventChannel(self, priority=lvl)
                self.first_chan.flow_que.append(f)

            elif lvl == self.first_chan.priority:
                self.first_chan.flow_que.append(f)

            elif lvl > self.first_chan.priority:
                chan = EventChannel(self, priority=lvl)
                chan.set_next(self.first_chan)
                self.first_chan = chan
                chan.flow_que.append(f)

            else:
                chan = self.first_chan
                while chan.next is not None and lvl <= chan.next.priority:
                    chan = chan.next

                if lvl == chan.priority:
                    chan.flow_que.append(f)
                else:
                    new_chan = EventChannel(self, priority=lvl)
                    chan_next = chan.next
                    new_chan.set_pre(chan)
                    new_chan.set_next(chan_next)
                    new_chan.flow_que.append(f)

            f._active = True

        logger.generic_lazy("以下处理流已添加：%s", lambda: repr(flows), level=LogLevel.DEBUG)

    def remove(self, *flows: Flow) -> None:
        for f in flows:
            f._active = False
        logger.generic_lazy("以下处理流不再生效：%s", lambda: repr(flows), level=LogLevel.DEBUG)

    def update(self, priority: int, *flows: Flow) -> None:
        self.remove(*flows)
        for f in flows:
            f.priority = priority
        self.add(*flows)
        logger.generic_lazy(
            f"以下处理流优先级更新为 {priority}：%s", lambda: repr(flows), level=LogLevel.DEBUG
        )

    def broadcast(self, event: Event) -> None:
        event.flag_set(self, self.HANDLED_FLOWS_FLAG, set())
        if self.first_chan is not None:
            self.first_chan.event_que.put_nowait(event)
        else:
            logger.debug(f"此刻没有可用的事件处理流，事件 {event.id} 将被丢弃")
            self._mark_dispatched(event)

    def _mark_dispatched(self, event: Event) -> None:
        event.flag_set(self, self.DISPATCHED_FLAG)


class EventChannel:
    def __init__(self, owner: Dispatcher, priority: int) -> None:
        self.owner = owner
        self.event_que: Queue[Event] = Queue()
        self.flow_que: deque[Flow] = deque()
        self.priority = priority

        self.pre: EventChannel | None = None
        self.next: EventChannel | None = None

        # 不要把 channel_ctx 先赋值给其他变量，后续再引用此变量，会导致上下文丢失
        if is_async_running():
            self.owner._channel_ctx.run(asyncio.create_task, self.run())
            logger.debug(f"pri={self.priority} 的通道已生成")
        else:
            register_loop_started_hook(
                lambda: self.owner._channel_ctx.run(asyncio.create_task, self.run())
            )
            logger.debug(f"pri={self.priority} 的通道已安排生成")

    def set_pre(self, pre: EventChannel | None) -> None:
        self.pre = pre
        if self.pre is not None:
            self.pre.next = self

    def set_next(self, next: EventChannel | None) -> None:
        self.next = next
        if self.next is not None:
            self.next.pre = self

    async def run(self) -> None:
        handle_tasks: list[Task] = []
        events: list[Event] = []
        valid_flows: list[Flow] = []

        while True:
            events.clear()
            if self.event_que.qsize() == 0:
                ev = await self.event_que.get()
                events.append(ev)
            for _ in range(self.event_que.qsize()):
                events.append(self.event_que.get_nowait())

            logger.debug(f"pri={self.priority} 通道开始处理 {len(events)} 个事件")
            for ev in events:
                handle_tasks.clear()
                valid_flows.clear()

                if len(self.flow_que) == 0:
                    self._dispose(*events)
                    return

                for _ in range(len(self.flow_que)):
                    handled_fs: set[Flow] = ev.flag_get(self.owner, self.owner.HANDLED_FLOWS_FLAG)
                    f = self.flow_que.popleft()
                    if f._active and f.priority == self.priority:
                        if f not in handled_fs:
                            handle_tasks.append(asyncio.create_task(f._handle(ev)))
                            handled_fs.add(f)
                        valid_flows.append(f)

                for f in valid_flows:
                    self.flow_que.append(f)
                if len(valid_flows):
                    coro = self._determine_spread(ev, handle_tasks)
                    asyncio.create_task(coro)
                else:
                    self._dispose(*events)
                    return

    def _dispose(self, *events: Event) -> None:
        if self.pre is not None:
            self.pre.set_next(self.next)
        if self.next is not None:
            for ev in events:
                self._try_pass_event(ev)
        if self is self.owner.first_chan:
            self.owner.first_chan = self.next

        logger.debug(f"pri={self.priority} 通道没有可用处理流，已销毁")

    async def _determine_spread(self, event: Event, handle_tasks: list[Task]) -> None:
        if not len(handle_tasks):
            self._try_pass_event(event)
            return

        logger.generic_lazy(
            "%s",
            lambda: f"pri={self.priority} 通道启动了 {len(handle_tasks)} 个处理流，事件：{repr(event)}",
            level=LogLevel.DEBUG,
        )
        await asyncio.wait(handle_tasks)
        logger.generic_lazy(
            "%s",
            lambda: f"pri={self.priority} 通道处理完成，事件：{repr(event)}",
            level=LogLevel.DEBUG,
        )
        self._try_pass_event(event)

    def _try_pass_event(self, event: Event) -> None:
        if self.next is not None and event.spread:
            self.next.event_que.put_nowait(event)
            chan = self.next
            logger.generic_lazy(
                "%s",
                lambda: f"事件向下一优先级 pri={chan.priority} 传播，事件：{repr(event)}",
                level=LogLevel.DEBUG,
            )
        else:
            self.owner._mark_dispatched(event)


async def wait_dispatched(event: Event, bot: "Bot") -> None:
    await event.flag_wait(bot._dispatcher, bot._dispatcher.DISPATCHED_FLAG, check_val=False)
