import asyncio
from typing import Any

from typing_extensions import TypeVar

from ..adapter.model import Event
from ..handle.base import EventHandler
from ..typ import HandleLevel
from ..utils import RWContext

KeyT = TypeVar("KeyT", bound=float, default=float)
ValT = TypeVar("ValT", default=Any)


class _KeyOrderDict(dict[KeyT, ValT]):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.update(*args, **kwargs)
        self.__buf: list[tuple[KeyT, ValT]] = []

    def __setitem__(self, key: KeyT, value: ValT) -> None:
        if len(self) == 0:
            return super().__setitem__(key, value)

        if key <= next(reversed(self.items()))[0]:
            return super().__setitem__(key, value)

        cnt = 0
        for k, _ in reversed(self.items()):
            if key > k:
                cnt += 1
            else:
                break

        for _ in range(cnt):
            self.__buf.append(self.popitem())
        super().__setitem__(key, value)
        while len(self.__buf):
            super().__setitem__(*self.__buf.pop())

        return None

    def update(self, *args: Any, **kwargs: Any) -> None:
        for k, v in dict(*args, **kwargs).items():
            self[k] = v

    def setdefault(self, key: KeyT, default: ValT) -> ValT:
        if key not in self:
            self[key] = default
        return self[key]


class Dispatcher:
    def __init__(self) -> None:
        self.handlers: _KeyOrderDict[HandleLevel, set[EventHandler]] = _KeyOrderDict()
        self.broadcast_ctrl = RWContext()
        self.gc_interval = 5

    def internal_add(self, *handlers: EventHandler) -> None:
        for h in handlers:
            self.handlers.setdefault(h.flow.priority, set()).add(h)
            h.flow.on_priority_reset(lambda new_prior, h=h: self.reset(h, new_prior))

    async def add(self, *handlers: EventHandler) -> None:
        async with self.broadcast_ctrl.write():
            self.internal_add(*handlers)

    async def _remove(self, *handlers: EventHandler) -> None:
        for h in handlers:
            await h.expire()
            h_set = self.handlers[h.flow.priority]
            h_set.remove(h)
            if len(h_set) == 0:
                self.handlers.pop(h.flow.priority)

    async def expire(self, *handlers: EventHandler) -> None:
        async with self.broadcast_ctrl.write():
            await self._remove(*handlers)

    async def reset(self, handler: EventHandler, new_prior: HandleLevel) -> None:
        if handler.flow.priority == new_prior:
            return

        async with self.broadcast_ctrl.write():
            old_prior = handler.flow.priority
            if old_prior == new_prior:
                return
            h_set = self.handlers[old_prior]
            h_set.remove(handler)
            if len(h_set) == 0:
                self.handlers.pop(old_prior)
            self.handlers.setdefault(new_prior, set()).add(handler)

    async def broadcast(self, event: Event) -> None:
        async with self.broadcast_ctrl.read():
            for h_set in self.handlers.values():
                tasks = tuple(asyncio.create_task(h.handle(event)) for h in h_set)
                await asyncio.wait(tasks)

                if not event.spread:
                    break

    async def timed_gc(self) -> None:
        while True:
            await asyncio.sleep(self.gc_interval)
            async with self.broadcast_ctrl.write():
                hs = tuple(
                    h for h_set in self.handlers.values() for h in h_set if h.invalid
                )
                await self._remove(*hs)
