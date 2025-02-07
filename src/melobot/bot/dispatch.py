from __future__ import annotations

import asyncio
from asyncio import Queue, Task, get_running_loop

from ..adapter.base import Event
from ..handle.base import Flow
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
            get_running_loop()
            asyncio.create_task(chan.run())
        except RuntimeError:
            self._pending_chans.append(chan)

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

    def remove(self, *flows: Flow) -> None:
        for f in flows:
            f._active = False

    def update(self, priority: int, *flows: Flow) -> None:
        self.remove(*flows)
        for f in flows:
            f.priority = priority
        self.add(*flows)

    def broadcast(self, event: Event) -> None:
        if self.first_chan is not None:
            self.first_chan.event_que.put_nowait(event)
        else:
            self.logger.warning(f"没有任何可用的事件处理流，事件 {event.id} 将被丢弃")

    def start(self) -> None:
        for chan in self._pending_chans:
            asyncio.create_task(chan.run())
        self._pending_chans.clear()


class EventChannel:
    def __init__(self, owner: Dispatcher, priority: int) -> None:
        self.owner = owner
        self.event_que: Queue[Event] = Queue()
        self.flow_que: Queue[Flow] = Queue()
        self.priority = priority

        self.pre: EventChannel | None = None
        self.next: EventChannel | None = None

        self.owner._arrange_chan(self)

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

    async def _determine_spread(self, ev: Event, handle_tasks: list[Task]) -> None:
        if not len(handle_tasks):
            if self.next is not None:
                self.next.event_que.put_nowait(ev)
            return

        await asyncio.wait(handle_tasks)
        if self.next is not None and ev.spread:
            self.next.event_que.put_nowait(ev)
