from __future__ import annotations

from dataclasses import dataclass
from itertools import tee
from typing import Iterable, NoReturn, Sequence

from ..adapter.model import Event
from ..ctx import FlowCtx, FlowRecord, FlowRecords
from ..ctx import FlowRecordStage as RecordStage
from ..ctx import FlowStatus, FlowStore
from ..di import DependNotMatched, inject_deps
from ..exceptions import FlowError
from ..typ import AsyncCallable, HandleLevel

_FLOW_CTX = FlowCtx()


def node(func: AsyncCallable[..., bool | None]) -> FlowNode:
    return FlowNode()(func)


def no_deps_node(func: AsyncCallable[..., bool | None]) -> FlowNode:
    return FlowNode()(func, no_deps=True)


class FlowNode:
    def __init__(self) -> None:
        self.name: str
        self.processor: AsyncCallable[..., bool | None]

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name})"

    def __call__(
        self, func: AsyncCallable[..., bool | None], no_deps: bool = False
    ) -> FlowNode:
        self.processor = func if no_deps else inject_deps(func)
        self.name = func.__name__
        return self

    async def process(self, event: Event, flow: Flow) -> None:
        try:
            status = _FLOW_CTX.get()
            records, store = status.records, status.store
        except _FLOW_CTX.lookup_exc_cls:
            records, store = FlowRecords(), FlowStore()

        with _FLOW_CTX.in_ctx(FlowStatus(event, flow, self, True, records, store)):
            try:
                records.append(
                    FlowRecord(RecordStage.NODE_START, flow.name, self.name, event)
                )

                try:
                    ret = await self.processor()
                    records.append(
                        FlowRecord(RecordStage.NODE_FINISH, flow.name, self.name, event)
                    )
                except DependNotMatched as e:
                    ret = False
                    records.append(
                        FlowRecord(
                            RecordStage.DEPENDS_NOT_MATCH,
                            flow.name,
                            self.name,
                            event,
                            f"Real({e.real_type}) <=> Annotation({e.hint})",
                        )
                    )

                if ret in (None, True) and _FLOW_CTX.get().next_valid:
                    await nextn()

            except FlowContinued:
                await nextn()


@dataclass
class _NodeInfo:
    nexts: list[FlowNode]
    in_deg: int
    out_deg: int

    def copy(self) -> _NodeInfo:
        return _NodeInfo(self.nexts, self.in_deg, self.out_deg)


class Flow:
    def __init__(
        self,
        name: str,
        *edge_maps: Iterable[Iterable[FlowNode] | FlowNode],
        priority: HandleLevel = HandleLevel.NORMAL,
        temp: bool = False,
    ) -> None:
        self.name = name
        self.temp = temp
        self.graph: dict[FlowNode, _NodeInfo] = {}

        self._priority = priority
        self._priority_cb: AsyncCallable[[HandleLevel], None]

        _edge_maps = tuple(
            tuple((elem,) if isinstance(elem, FlowNode) else elem for elem in emap)
            for emap in edge_maps
        )
        edges = self._get_edges(_edge_maps)

        for n1, n2 in edges:
            self._add(n1, n2)

        if not self._valid_check():
            raise FlowError(f"定义的处理流 {self.name} 中存在环路")

    def _get_edges(
        self, edge_maps: Sequence[Sequence[Iterable[FlowNode]]]
    ) -> list[tuple[FlowNode, FlowNode]]:
        edges: list[tuple[FlowNode, FlowNode]] = []

        for emap in edge_maps:
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

        return edges

    @property
    def priority(self) -> HandleLevel:
        return self._priority

    def on_priority_reset(self, callback: AsyncCallable[[HandleLevel], None]) -> None:
        self._priority_cb = callback

    async def reset_priority(self, new_prior: HandleLevel) -> None:
        await self._priority_cb(new_prior)
        self._priority = new_prior

    @property
    def starts(self) -> tuple[FlowNode, ...]:
        return tuple(n for n, info in self.graph.items() if info.in_deg == 0)

    @property
    def ends(self) -> tuple[FlowNode, ...]:
        return tuple(n for n, info in self.graph.items() if info.out_deg == 0)

    def __repr__(self) -> str:
        output = f"{self.__class__.__name__}(name={self.name}, nums={len(self.graph)}"

        if len(self.graph):
            output += f", starts=[{', '.join(repr(n) for n in self.starts)}])"
        else:
            output += ")"
        return output

    def _add(self, _from: FlowNode, to: FlowNode | None) -> None:
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

    def link(self, flow: Flow, priority: HandleLevel | None = None) -> Flow:
        # pylint: disable=protected-access
        _froms = self.ends
        _tos = flow.starts
        new_edges = tuple((n1, n2) for n1 in _froms for n2 in _tos)

        new_flow = Flow(
            f"{self.name} ~ {flow.name}",
            *new_edges,
            priority=priority if priority else min(self.priority, flow.priority),
            temp=self.temp or flow.temp,
        )

        for n1, info in (self.graph | flow.graph).items():
            if not len(info.nexts):
                new_flow._add(n1, None)
                continue
            for n2 in info.nexts:
                new_flow._add(n1, n2)

        if not self._valid_check():
            raise FlowError(f"定义的处理流 {self.name} 中存在环路")

        return new_flow

    async def run(self, event: Event) -> None:
        if not len(self.starts):
            return

        try:
            status = _FLOW_CTX.get()
            records, store = status.records, status.store
        except _FLOW_CTX.lookup_exc_cls:
            records, store = FlowRecords(), FlowStore()

        with _FLOW_CTX.in_ctx(
            FlowStatus(event, self, self.starts[0], True, records, store)
        ):
            try:
                records.append(
                    FlowRecord(
                        RecordStage.FLOW_START, self.name, self.starts[0].name, event
                    )
                )

                idx = 0
                while idx < len(self.starts):
                    try:
                        await self.starts[idx].process(event, self)
                        idx += 1
                    except FlowRewound:
                        pass

                records.append(
                    FlowRecord(
                        RecordStage.FLOW_FINISH, self.name, self.starts[0].name, event
                    )
                )
            except FlowBroke:
                pass


class _FlowSignal(BaseException): ...


class FlowBroke(_FlowSignal): ...


class FlowContinued(_FlowSignal): ...


class FlowRewound(_FlowSignal): ...


async def nextn() -> None:
    try:
        status = _FLOW_CTX.get()
        nexts = status.flow.graph[status.node].nexts
        if not status.next_valid:
            return

        idx = 0
        while idx < len(nexts):
            try:
                await nexts[idx].process(status.event, status.flow)
                idx += 1
            except FlowRewound:
                pass

    except _FLOW_CTX.lookup_exc_cls:
        raise FlowError("此时不在活动的事件处理流中，无法调用下一处理结点") from None
    finally:
        status.next_valid = False


async def block() -> None:
    status = _FLOW_CTX.get()
    status.records.append(
        FlowRecord(RecordStage.BLOCK, status.flow.name, status.node.name, status.event)
    )
    status.event.spread = False


async def stop() -> NoReturn:
    status = _FLOW_CTX.get()
    status.records.append(
        FlowRecord(RecordStage.STOP, status.flow.name, status.node.name, status.event)
    )
    status.records.append(
        FlowRecord(
            RecordStage.NODE_EARLY_FINISH,
            status.flow.name,
            status.node.name,
            status.event,
        )
    )
    status.records.append(
        FlowRecord(
            RecordStage.FLOW_EARLY_FINISH,
            status.flow.name,
            status.node.name,
            status.event,
        )
    )
    raise FlowBroke("事件处理流被安全地提早结束，请无视这个内部工作信号")


async def bypass() -> NoReturn:
    status = _FLOW_CTX.get()
    status.records.append(
        FlowRecord(RecordStage.BYPASS, status.flow.name, status.node.name, status.event)
    )
    status.records.append(
        FlowRecord(
            RecordStage.NODE_EARLY_FINISH,
            status.flow.name,
            status.node.name,
            status.event,
        )
    )
    raise FlowContinued("事件处理流安全地跳过结点执行，请无视这个内部工作信号")


async def rewind() -> NoReturn:
    status = _FLOW_CTX.get()
    status.records.append(
        FlowRecord(RecordStage.REWIND, status.flow.name, status.node.name, status.event)
    )
    status.records.append(
        FlowRecord(
            RecordStage.NODE_EARLY_FINISH,
            status.flow.name,
            status.node.name,
            status.event,
        )
    )
    raise FlowRewound("事件处理流安全地重复执行处理结点，请无视这个内部工作信号")


async def flow_to(flow: Flow) -> None:
    status = _FLOW_CTX.get()
    await flow.run(status.event)
