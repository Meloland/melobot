from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from itertools import tee

from ..adapter.base import Event, Event_T
from ..exceptions import ProcessFlowError
from ..session.base import Session
from ..session.option import SessionOption
from ..typing import AsyncCallable, Generic, HandleLevel, Iterable


class ProcessNode:
    def __init__(self, type: type[Event] = Event, name: str = "") -> None:
        self.name = name
        self.type = type
        self.processor: AsyncCallable[..., bool | None]

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, type={self.type})"

    def __call__(self, func: AsyncCallable[..., bool | None]) -> ProcessNode:
        self.processor = func
        if self.name == "":
            self.name = func.__name__
        return self

    async def process(self, flow: ProcessFlow) -> None:
        # TODO: 完成依赖注入操作
        if not isinstance(Session.current_event(), self.type):
            return

        try:
            stack = _FLOW_CTX.get().stack
        except LookupError:
            stack = []

        try:
            token = _FLOW_CTX.set(_FlowCtx(flow, self, True, stack))
            stack.append(f"[{flow.name}] | Start -> <{self.name}>")
            ret = await self.processor()
            stack.append(f"[{flow.name}] | <{self.name}> -> Finished")
            if ret in (None, True) and _FLOW_CTX.get().next_valid:
                await nextp()

        except FlowContinued:
            await nextp()
        finally:
            _FLOW_CTX.reset(token)


@dataclass
class _NodeInfo:
    nexts: list[ProcessNode]
    in_deg: int
    out_deg: int

    def copy(self) -> _NodeInfo:
        return _NodeInfo(self.nexts, self.in_deg, self.out_deg)


class ProcessFlow(Generic[Event_T]):
    def __init__(
        self,
        name: str,
        *edge_maps: Iterable[Iterable[ProcessNode] | ProcessNode],
        event_type: type[Event] = Event,
        priority: HandleLevel = HandleLevel.NORMAL,
        temp: bool = False,
        option: SessionOption[Event_T] | None = None,
    ) -> None:
        self.name = name
        self.event_type = event_type
        self.priority = priority
        self.temp = temp
        self.option = option

        edges: list[tuple[ProcessNode, ProcessNode]] = []
        self.graph: dict[ProcessNode, _NodeInfo] = {}

        _edge_maps = (
            tuple((elem,) if isinstance(elem, ProcessNode) else elem for elem in emap)
            for emap in edge_maps
        )

        for emap in _edge_maps:
            iter1, iter2 = tee(emap, 2)
            try:
                next(iter2)
            except StopIteration:
                continue
            if len(emap) == 1:
                for n in emap[0]:
                    self._add(n, None)
                continue
            for from_seq, to_seq in zip(iter1, iter2):
                for n1 in from_seq:
                    for n2 in to_seq:
                        if (n1, n2) not in edges:
                            edges.append((n1, n2))

        for n1, n2 in edges:
            self._add(n1, n2)
        if not self._valid_check():
            raise ProcessFlowError(f"定义的处理流{self.name}中存在环路")

    @property
    def starts(self) -> tuple[ProcessNode, ...]:
        return tuple(n for n, info in self.graph.items() if info.in_deg == 0)

    @property
    def ends(self) -> tuple[ProcessNode, ...]:
        return tuple(n for n, info in self.graph.items() if info.out_deg == 0)

    def __repr__(self) -> str:
        output = f"{self.__class__.__name__}(name={self.name}, nums={len(self.graph)}"
        if len(self.graph):
            output += f", starts=[{', '.join(repr(n) for n in self.starts)}])"
        else:
            output += ")"
        return output

    def _add(self, _from: ProcessNode, to: ProcessNode | None) -> None:
        from_info = self.graph.setdefault(_from, _NodeInfo([], 0, 0))
        if to is not None:
            to_info = self.graph.setdefault(to, _NodeInfo([], 0, 0))
            to_info.in_deg += 1
            from_info.out_deg += 1
            from_info.nexts.append(to)

    def _valid_check(self) -> bool:
        graph = {n: info.copy() for n, info in self.graph.items()}
        while len(graph):
            for n, info in graph.items():
                nexts, in_deg = info.nexts, info.in_deg
                if in_deg == 0:
                    graph.pop(n)
                    for next_n in nexts:
                        graph[next_n].in_deg -= 1
                    break
            else:
                return False
        return True

    async def _run(self) -> None:
        try:
            stack = _FLOW_CTX.get().stack
        except LookupError:
            stack = []

        token = _FLOW_CTX.set(_FlowCtx(self, self.starts[0], True, stack))
        try:
            stack.append(f"[{self.name}] | Start >>> [{self.name}]")
            idx = 0
            while idx < len(self.starts):
                try:
                    await self.starts[idx].process(self)
                    idx += 1
                except FlowRewound:
                    pass
            stack.append(f"[{self.name}] | [{self.name}] >>> Finished")
        except FlowBroke:
            pass
        finally:
            _FLOW_CTX.reset(token)


@dataclass
class _FlowCtx:
    flow: ProcessFlow
    node: ProcessNode
    next_valid: bool
    stack: list[str]


_FLOW_CTX: ContextVar[_FlowCtx] = ContextVar("_FLOW_CTX")


class _FlowSignal(BaseException):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class FlowBroke(_FlowSignal):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class FlowContinued(_FlowSignal):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class FlowRewound(_FlowSignal):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


async def nextp() -> None:
    try:
        ctx = _FLOW_CTX.get()
        nexts = ctx.flow.graph[ctx.node].nexts
        if not ctx.next_valid:
            return

        idx = 0
        while idx < len(nexts):
            try:
                await nexts[idx].process(ctx.flow)
                idx += 1
            except FlowRewound:
                pass

    except LookupError:
        raise ProcessFlowError("此刻不在活动的处理流中，无法调用下一处理结点")
    finally:
        ctx.next_valid = False


async def block() -> None:
    ctx = _FLOW_CTX.get()
    ctx.stack.append(f"[{ctx.flow.name}] | <{ctx.node.name}> ~ [BLOCK]")
    Session.current_event()._spread = False


async def quit() -> None:
    ctx = _FLOW_CTX.get()
    ctx.stack.append(f"[{ctx.flow.name}] | <{ctx.node.name}> ~ [QUIT]")
    ctx.stack.append(f"[{ctx.flow.name}] | <{ctx.node.name}> -> Early Finished")
    ctx.stack.append(f"[{ctx.flow.name}] | [{ctx.flow.name}] >>> Early Finished")
    raise FlowBroke("事件处理流被安全地提早结束，请无视这个内部工作信号")


async def bypass() -> None:
    ctx = _FLOW_CTX.get()
    ctx.stack.append(f"[{ctx.flow.name}] | <{ctx.node.name}> ~ [BYPASS]")
    ctx.stack.append(f"[{ctx.flow.name}] | <{ctx.node.name}> -> Early Finished")
    raise FlowContinued("事件处理流安全地跳过结点执行，请无视这个内部工作信号")


async def rewind() -> None:
    ctx = _FLOW_CTX.get()
    ctx.stack.append(f"[{ctx.flow.name}] | <{ctx.node.name}> ~ [REWIND]")
    ctx.stack.append(f"[{ctx.flow.name}] | <{ctx.node.name}> -> Early Finished")
    raise FlowRewound("事件处理流安全地重复执行处理结点，请无视这个内部工作信号")


async def flow_to(flow: ProcessFlow) -> None:
    await flow._run()


def get_flow_stack() -> tuple[str, ...]:
    return tuple(_FLOW_CTX.get().stack)
