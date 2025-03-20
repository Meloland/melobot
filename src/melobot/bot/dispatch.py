from __future__ import annotations

import asyncio
from asyncio import Queue, Task

from ..adapter.base import Event
from ..handle.base import Flow
from ..log.base import LogLevel
from ..mixin import LogMixin


class Dispatcher(LogMixin):
    def __init__(self) -> None:
        self.first_chan: EventChannel | None = None

        self._pending_chans: list[EventChannel] = []

    def __repr__(self) -> str:
        counts: dict[int, str] = {}
        chan = self.first_chan
        while chan is not None:
            counts[chan.priority] = (
                f"[flows:{chan.flow_que.qsize()}, events:{chan.event_que.qsize()}]"
            )
            chan = chan.next
        return f"{self.__class__.__name__}({counts})"

    def _arrange_chan(self, chan: EventChannel) -> None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            self._pending_chans.append(chan)
        else:
            asyncio.create_task(chan.run())

    def add(self, *flows: Flow) -> None:
        for f in flows:
            lvl = f.priority

            if self.first_chan is None:
                self.first_chan = EventChannel(self, priority=lvl)
                self.first_chan.flow_que.put_nowait(f)

            elif lvl == self.first_chan.priority:
                self.first_chan.flow_que.put_nowait(f)

            elif lvl > self.first_chan.priority:
                chan = EventChannel(self, priority=lvl)
                chan.set_next(self.first_chan)
                self.first_chan = chan
                chan.flow_que.put_nowait(f)

            else:
                chan = self.first_chan
                while chan.next is not None and lvl <= chan.next.priority:
                    chan = chan.next

                if lvl == chan.priority:
                    chan.flow_que.put_nowait(f)
                else:
                    new_chan = EventChannel(self, priority=lvl)
                    chan_next = chan.next
                    new_chan.set_pre(chan)
                    new_chan.set_next(chan_next)
                    new_chan.flow_que.put_nowait(f)

            f._active = True

        self.logger.generic_lazy("以下处理流已添加：%s", lambda: repr(flows), level=LogLevel.DEBUG)

    def remove(self, *flows: Flow) -> None:
        for f in flows:
            f._active = False
        self.logger.generic_lazy(
            "以下处理流不再生效：%s", lambda: repr(flows), level=LogLevel.DEBUG
        )

    def update(self, priority: int, *flows: Flow) -> None:
        self.remove(*flows)
        for f in flows:
            f.priority = priority
        self.add(*flows)
        self.logger.generic_lazy(
            f"以下处理流优先级更新为 {priority}：%s", lambda: repr(flows), level=LogLevel.DEBUG
        )

    def broadcast(self, event: Event) -> None:
        if self.first_chan is not None:
            self.first_chan.event_que.put_nowait(event)
        else:
            self.logger.debug(f"此刻没有可用的事件处理流，事件 {event.id} 将被丢弃")

    def start(self) -> None:
        for chan in self._pending_chans:
            asyncio.create_task(chan.run())
        self._pending_chans.clear()


class EventChannel(LogMixin):
    def __init__(self, owner: Dispatcher, priority: int) -> None:
        self.owner = owner
        self.event_que: Queue[Event] = Queue()
        self.flow_que: Queue[Flow] = Queue()
        self.priority = priority

        self.pre: EventChannel | None = None
        self.next: EventChannel | None = None

        self.owner._arrange_chan(self)
        self.logger.debug(f"pri={self.priority} 的通道已生成")

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

            self.logger.debug(f"pri={self.priority} 通道开始处理 {len(events)} 个事件")
            for ev in events:
                ev.flag_set_default(self.owner, self.owner, set())
                handle_tasks.clear()
                valid_flows.clear()

                if self.flow_que.qsize() == 0:
                    self._dispose(*events)
                    return

                for _ in range(self.flow_que.qsize()):
                    handled_fs: set[Flow] = ev.flag_get(self.owner, self.owner)
                    f = self.flow_que.get_nowait()
                    if f._active and f.priority == self.priority:
                        if f not in handled_fs:
                            handle_tasks.append(asyncio.create_task(f._handle(ev)))
                            handled_fs.add(f)
                        valid_flows.append(f)

                for f in valid_flows:
                    self.flow_que.put_nowait(f)
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
                self.next.event_que.put_nowait(ev)
        if self is self.owner.first_chan:
            self.owner.first_chan = self.next

        self.logger.debug(f"pri={self.priority} 通道没有可用处理流，已销毁")

    async def _determine_spread(self, ev: Event, handle_tasks: list[Task]) -> None:
        if not len(handle_tasks):
            if self.next is not None:
                self.next.event_que.put_nowait(ev)
            return

        self.logger.generic_lazy(
            f"pri={self.priority} 通道启动了 {len(handle_tasks)} 个处理流，事件：%s",
            lambda: repr(ev),
            level=LogLevel.DEBUG,
        )
        await asyncio.wait(handle_tasks)
        self.logger.generic_lazy(
            f"pri={self.priority} 通道处理完成，事件：%s", lambda: repr(ev), level=LogLevel.DEBUG
        )

        if self.next is not None and ev.spread:
            self.logger.generic_lazy(
                f"事件向下一优先级 pri={self.next.priority} 传播，事件：%s",
                lambda: repr(ev),
                level=LogLevel.DEBUG,
            )
            self.next.event_que.put_nowait(ev)
