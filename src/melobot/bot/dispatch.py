import asyncio

from ..adapter.abc import Event
from ..plugin.handler import EventHandler, HandleLevel
from ..typing import TypeVar
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


class EventBus:
    def __init__(self) -> None:
        self.handlers: _KeyOrderDict[HandleLevel, set[EventHandler]] = _KeyOrderDict()
        self.broadcast_ctrl = RWContext()

    async def add(self, *handlers: EventHandler) -> None:
        async with self.broadcast_ctrl.write():
            for h in handlers:
                self.handlers.setdefault(h.priority, set()).add(h)

    async def remove(self, *handlers: EventHandler) -> None:
        async with self.broadcast_ctrl.write():
            for h in handlers:
                await h.expire()
                self.handlers[h.priority].remove(h)

    async def broadcast(self, event: Event) -> None:
        async with self.broadcast_ctrl.read():
            for h_set in self.handlers.values():
                tasks = tuple(asyncio.create_task(h.handle(event)) for h in h_set)

                can_spread = True
                for fut in asyncio.as_completed(tasks):
                    if not (await fut):
                        can_spread = False

                if not can_spread:
                    break
