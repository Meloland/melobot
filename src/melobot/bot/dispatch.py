import asyncio

from ..adapter.model import Event
from ..handle.base import EventHandler
from ..typing import HandleLevel, TypeVar
from ..utils import RWContext

key_T = TypeVar("key_T", bound=float)
val_T = TypeVar("val_T")


class _KeyOrderDict(dict[key_T, val_T]):
    def __init__(self, *args, **kwargs) -> None:
        self.update(*args, **kwargs)
        self.__buf: list[tuple[key_T, val_T]] = []

    def __setitem__(self, key: key_T, value: val_T) -> None:
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

    def update(self, *args, **kwargs):
        for k, v in dict(*args, **kwargs).items():
            self[k] = v

    def setdefault(self, key: key_T, default: val_T) -> val_T:
        if key not in self:
            self[key] = default
        return self[key]


class Dispatcher:
    def __init__(self) -> None:
        self.handlers: _KeyOrderDict[HandleLevel, set[EventHandler]] = _KeyOrderDict()
        self.broadcast_ctrl = RWContext()
        self.gc_interval = 5

    def no_ctrl_add(self, *handlers: EventHandler) -> None:
        for h in handlers:
            self.handlers.setdefault(h.priority, set()).add(h)

    async def add(self, *handlers: EventHandler) -> None:
        async with self.broadcast_ctrl.write():
            self.no_ctrl_add(*handlers)

    async def __remove(self, *handlers: EventHandler) -> None:
        for h in handlers:
            await h.expire()
            h_set = self.handlers[h.priority]
            h_set.remove(h)
            if len(h_set) == 0:
                self.handlers.pop(h.priority)

    async def expire(self, *handlers: EventHandler) -> None:
        async with self.broadcast_ctrl.write():
            await self.__remove(*handlers)

    async def reset(self, handler: EventHandler, new_prior: HandleLevel) -> None:
        async with self.broadcast_ctrl.write():
            old_prior = handler.priority
            h_set = self.handlers[old_prior]
            h_set.remove(handler)
            if len(h_set) == 0:
                self.handlers.pop(old_prior)
            self.handlers.setdefault(new_prior, set()).add(handler)
            await handler.reset_prior(new_prior)

    async def broadcast(self, event: Event) -> None:
        async with self.broadcast_ctrl.read():
            for h_set in self.handlers.values():
                tasks = tuple(asyncio.create_task(h.handle(event)) for h in h_set)
                await asyncio.wait(tasks)

                if not event._spread:
                    break

    async def timed_gc(self) -> None:
        while True:
            await asyncio.sleep(self.gc_interval)
            async with self.broadcast_ctrl.write():
                hs = tuple(
                    h for h_set in self.handlers.values() for h in h_set if h._invalid
                )
                await self.__remove(*hs)
