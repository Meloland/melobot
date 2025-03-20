from __future__ import annotations

from asyncio import create_task, get_running_loop
from dataclasses import dataclass
from itertools import tee

from typing_extensions import Iterable, NoReturn, Sequence

from .._run import report_exc
from ..adapter.base import Event
from ..ctx import BotCtx, EventCompletion, FlowCtx, FlowRecord, FlowRecords
from ..ctx import FlowRecordStage as RecordStage
from ..ctx import FlowStatus, FlowStore
from ..di import DependNotMatched, inject_deps
from ..exceptions import FlowError
from ..typ.base import AsyncCallable, SyncOrAsyncCallable
from ..utils.base import to_async
from ..utils.common import get_obj_name

_FLOW_CTX = FlowCtx()


def node(func: SyncOrAsyncCallable[..., bool | None]) -> FlowNode:
    """处理结点装饰器，将当前异步可调用对象装饰为一个处理结点"""
    return FlowNode(func)


def no_deps_node(func: SyncOrAsyncCallable[..., bool | None]) -> FlowNode:
    """与 :func:`node` 类似，但是不自动为结点标记依赖注入。

    需要后续使用 :func:`.inject_deps` 手动标记依赖注入，
    这适用于某些对处理结点进行再装饰的情况
    """
    return FlowNode(func, no_deps=True)


class FlowNode:
    """处理流结点"""

    def __init__(self, func: SyncOrAsyncCallable[..., bool | None], no_deps: bool = False) -> None:
        self.name = get_obj_name(func, otype="callable")
        self.processor: AsyncCallable[..., bool | None] = (
            to_async(func) if no_deps else inject_deps(func)
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name})"

    async def process(self, flow: Flow, completion: EventCompletion) -> None:
        event = completion.event
        try:
            status = _FLOW_CTX.get()
            records, store = status.records, status.store
        except _FLOW_CTX.lookup_exc_cls:
            records, store = FlowRecords(), FlowStore()

        with _FLOW_CTX.unfold(FlowStatus(flow, self, True, completion, records, store)):
            try:
                records.append(FlowRecord(RecordStage.NODE_START, flow.name, self.name, event))

                try:
                    ret = await self.processor()
                    records.append(FlowRecord(RecordStage.NODE_FINISH, flow.name, self.name, event))
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
class NodeInfo:
    nexts: list[FlowNode]
    in_deg: int
    out_deg: int

    def copy(self) -> NodeInfo:
        return NodeInfo(self.nexts, self.in_deg, self.out_deg)


class Flow:
    """处理流

    :ivar str name: 处理流的标识
    """

    def __init__(
        self,
        name: str,
        *edge_maps: Iterable[Iterable[FlowNode] | FlowNode],
        priority: int = 0,
    ) -> None:
        """初始化处理流

        :param name: 处理流的标识
        :param edge_maps: 边映射，遵循 melobot 的 graph edges 表示方法
        :param priority: 处理流的优先级
        """
        self.name = name
        self.graph: dict[FlowNode, NodeInfo] = {}
        self.priority = priority

        self._active = True

        _edge_maps = tuple(
            tuple((elem,) if isinstance(elem, FlowNode) else elem for elem in emap)
            for emap in edge_maps
        )
        edges = self._get_edges(_edge_maps)

        for n1, n2 in edges:
            self._add(n1, n2)

        if not self._valid_check():
            raise FlowError(f"定义的处理流 {self.name} 中存在环路")

    def __repr__(self) -> str:
        output = (
            f"{self.__class__.__name__}(name={self.name}, active={self._active}"
            f", pri={self.priority}, nums={len(self.graph)}"
        )

        if len(self.graph):
            output += f", starts=[{', '.join(n.name for n in self.starts)}])"
        else:
            output += ")"
        return output

    @property
    def starts(self) -> tuple[FlowNode, ...]:
        return tuple(n for n, info in self.graph.items() if info.in_deg == 0)

    @property
    def ends(self) -> tuple[FlowNode, ...]:
        return tuple(n for n, info in self.graph.items() if info.out_deg == 0)

    def update_priority(self, priority: int) -> None:
        """更新处理流优先级

        :param priority: 新优先级
        """
        BotCtx().get()._dispatcher.update(priority, self)

    def dismiss(self) -> None:
        """停用处理流

        停用后将无法处理任何新事件，也无法再次恢复使用
        """
        self._active = False

    def is_active(self) -> bool:
        """判断处理流是否处于可用状态

        :return: 是否可用
        """
        return self._active

    def link(self, flow: Flow, priority: int | None = None) -> Flow:
        """连接另一处理流返回新处理流，并设置新优先级

        :param flow: 连接的新流
        :param priority: 新优先级，若为空，则使用两者中较小的优先级
        :return: 新的处理流
        """
        _froms = self.ends
        _tos = flow.starts
        new_edges = tuple((n1, n2) for n1 in _froms for n2 in _tos)

        new_flow = Flow(
            f"{self.name} ~ {flow.name}",
            *new_edges,
            priority=priority if priority else min(self.priority, flow.priority),
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

    def _add(self, _from: FlowNode, to: FlowNode | None) -> None:
        from_info = self.graph.setdefault(_from, NodeInfo([], 0, 0))

        if to is not None:
            to_info = self.graph.setdefault(to, NodeInfo([], 0, 0))
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

    async def _handle(self, event: Event) -> None:
        fut = get_running_loop().create_future()
        create_task(self._run(EventCompletion(event, fut, self)))
        await fut

    async def _run(self, completion: EventCompletion) -> None:
        if not len(self.starts):
            if (
                completion.owner_flow is self
                and not completion.under_session
                and not completion.completed.done()
            ):
                completion.completed.set_result(None)
            return

        event = completion.event
        try:
            status = _FLOW_CTX.get()
            records, store = status.records, status.store
        except _FLOW_CTX.lookup_exc_cls:
            records, store = FlowRecords(), FlowStore()

        with _FLOW_CTX.unfold(FlowStatus(self, self.starts[0], True, completion, records, store)):
            try:
                records.append(
                    FlowRecord(RecordStage.FLOW_START, self.name, self.starts[0].name, event)
                )

                idx = 0
                while idx < len(self.starts):
                    try:
                        await self.starts[idx].process(self, completion)
                        idx += 1
                    except FlowRewound:
                        pass

                records.append(
                    FlowRecord(RecordStage.FLOW_FINISH, self.name, self.starts[0].name, event)
                )

            except FlowBroke:
                pass

            except Exception as e:
                report_exc(
                    e,
                    msg=f"事件处理流 {self.name} 发生异常",
                    var={
                        "event_id": event.id,
                        "event": event,
                        "completion": completion.__dict__,
                        "cur_flow": self,
                    },
                )

            finally:
                if (
                    completion.owner_flow is self
                    and not completion.under_session
                    and not completion.completed.done()
                ):
                    completion.completed.set_result(None)


class _FlowSignal(BaseException): ...


class FlowBroke(_FlowSignal): ...


class FlowContinued(_FlowSignal): ...


class FlowRewound(_FlowSignal): ...


async def nextn() -> None:
    """运行下一处理结点（在处理流中使用）"""
    try:
        status = _FLOW_CTX.get()
        nexts = status.flow.graph[status.node].nexts
        if not status.next_valid:
            return

        idx = 0
        while idx < len(nexts):
            try:
                await nexts[idx].process(status.flow, status.completion)
                idx += 1
            except FlowRewound:
                pass

    except _FLOW_CTX.lookup_exc_cls:
        raise FlowError("此时不在活动的事件处理流中，无法调用下一处理结点") from None
    finally:
        status.next_valid = False


async def block() -> None:
    """阻止当前事件向更低优先级的处理流传播（在处理流中使用）"""
    status = _FLOW_CTX.get()
    status.records.append(
        FlowRecord(RecordStage.BLOCK, status.flow.name, status.node.name, status.completion.event)
    )
    status.completion.event.spread = False


async def stop() -> NoReturn:
    """立即停止当前处理流（在处理流中使用）"""
    status = _FLOW_CTX.get()
    status.records.append(
        FlowRecord(RecordStage.STOP, status.flow.name, status.node.name, status.completion.event)
    )
    status.records.append(
        FlowRecord(
            RecordStage.NODE_EARLY_FINISH,
            status.flow.name,
            status.node.name,
            status.completion.event,
        )
    )
    status.records.append(
        FlowRecord(
            RecordStage.FLOW_EARLY_FINISH,
            status.flow.name,
            status.node.name,
            status.completion.event,
        )
    )
    raise FlowBroke("事件处理流被安全地提早结束，请无视这个内部工作信号")


async def bypass() -> NoReturn:
    """立即跳过当前处理结点剩下的步骤，运行下一处理结点（在处理流中使用）"""
    status = _FLOW_CTX.get()
    status.records.append(
        FlowRecord(
            RecordStage.BYPASS,
            status.flow.name,
            status.node.name,
            status.completion.event,
        )
    )
    status.records.append(
        FlowRecord(
            RecordStage.NODE_EARLY_FINISH,
            status.flow.name,
            status.node.name,
            status.completion.event,
        )
    )
    raise FlowContinued("事件处理流安全地跳过结点执行，请无视这个内部工作信号")


async def rewind() -> NoReturn:
    """立即重新运行当前处理结点（在处理流中使用）"""
    status = _FLOW_CTX.get()
    status.records.append(
        FlowRecord(
            RecordStage.REWIND,
            status.flow.name,
            status.node.name,
            status.completion.event,
        )
    )
    status.records.append(
        FlowRecord(
            RecordStage.NODE_EARLY_FINISH,
            status.flow.name,
            status.node.name,
            status.completion.event,
        )
    )
    raise FlowRewound("事件处理流安全地重复执行处理结点，请无视这个内部工作信号")


async def flow_to(flow: Flow) -> None:
    """立即进入一个其他处理流（在处理流中使用）"""
    status = _FLOW_CTX.get()
    await flow._run(status.completion)
