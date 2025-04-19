from __future__ import annotations

from asyncio import create_task, get_running_loop

from typing_extensions import Callable, Iterable, NoReturn

from ..adapter.base import Event
from ..ctx import BotCtx, EventCompletion, FlowCtx, FlowRecord, FlowRecords
from ..ctx import FlowRecordStage as RecordStage
from ..ctx import FlowStatus, FlowStore
from ..di import DependNotMatched, inject_deps
from ..exceptions import FlowError
from ..log.report import log_exc
from ..typ.base import AsyncCallable, P, SyncOrAsyncCallable
from ..utils.base import to_async
from ..utils.common import get_obj_name
from .graph import DAGMapping

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


class Flow:
    """处理流

    :ivar str name: 处理流的标识
    """

    def __init__(
        self,
        name: str,
        *edge_maps: Iterable[Iterable[FlowNode] | FlowNode],
        priority: int = 0,
        guard: SyncOrAsyncCallable[[Event], bool | None] | None = None,
    ) -> None:
        """初始化处理流

        :param name: 处理流的标识
        :param edge_maps: 边映射，遵循 melobot 的 graph edges 表示方法
        :param priority: 处理流的优先级
        :param guard: 守卫函数。在处理流运行前调用，返回 `True` 不再继续运行处理流。默认不启用
        """
        self.name = name
        self.graph = DAGMapping[FlowNode](name, *edge_maps)
        self.priority = priority

        self._active = True
        self._guard = to_async(guard) if guard is not None else None

    @staticmethod
    def from_graph(
        name: str,
        graph: DAGMapping[FlowNode],
        priority: int = 0,
        guard: SyncOrAsyncCallable[[Event], bool | None] | None = None,
    ) -> Flow:
        f = Flow(name, priority=priority, guard=guard)
        f.graph = graph
        return f

    def __repr__(self) -> str:
        output = (
            f"{self.__class__.__name__}(name={self.name}, active={self._active}"
            f", pri={self.priority}, nums={len(self.graph)}"
        )

        if len(self.graph):
            output += f", starts:{len(self.graph.starts)})"
        else:
            output += ")"
        return output

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

    def set_guard(self, guard: SyncOrAsyncCallable[[Event], bool | None]) -> None:
        """设置或重设守卫函数

        :param guard: 守卫函数
        """
        self._guard = to_async(guard) if guard is not None else None

    def link(self, flow: Flow, priority: int | None = None) -> Flow:
        """连接另一处理流返回新处理流，并设置新优先级

        新处理流守卫函数为空，使用 :meth:`set_guard` 自行添加

        :param flow: 连接的新流
        :param priority: 新优先级，若为空，则使用两者中较小的优先级
        :return: 新的处理流
        """
        name = f"{self.name} ~ {flow.name}"
        new_flow = Flow.from_graph(
            name,
            self.graph.link(flow.graph, name),
            priority=priority if priority else min(self.priority, flow.priority),
        )
        return new_flow

    def start(self, node: FlowNode) -> FlowNode:
        self.graph.add(node, None)
        return node

    def after(self, node: FlowNode) -> Callable[[FlowNode], FlowNode]:
        def after_wrapped(next_node: FlowNode) -> FlowNode:
            self.graph.add(node, next_node)
            return next_node

        return after_wrapped

    def before(self, node: FlowNode) -> Callable[[FlowNode], FlowNode]:
        def before_wrapped(pre_node: FlowNode) -> FlowNode:
            self.graph.add(pre_node, node)
            return pre_node

        return before_wrapped

    def merge(self, *nodes: FlowNode) -> Callable[[FlowNode], FlowNode]:
        def merge_wrapped(next_node: FlowNode) -> FlowNode:
            for node in nodes:
                self.graph.add(node, next_node)
            return next_node

        return merge_wrapped

    def fork(self, *nodes: FlowNode) -> Callable[[FlowNode], FlowNode]:
        def fork_wrapped(pre_node: FlowNode) -> FlowNode:
            for node in nodes:
                self.graph.add(pre_node, node)
            return pre_node

        return fork_wrapped

    async def _handle(self, event: Event) -> None:
        fut = get_running_loop().create_future()
        create_task(self._run(EventCompletion(event, fut, self)))
        await fut

    async def _run(self, completion: EventCompletion) -> None:
        if self._guard is not None:
            try:
                if not await self._guard(completion.event):
                    return self._try_set_completed(completion)
            except Exception as e:
                log_exc(
                    e,
                    msg=f"事件处理流 {self.name} 守卫函数发生异常",
                    obj={
                        "event_id": completion.event.id,
                        "event": completion.event,
                        "guard": self._guard,
                    },
                )
                return self._try_set_completed(completion)

        starts = self.graph.starts
        if not len(starts):
            return self._try_set_completed(completion)

        event = completion.event
        try:
            status = _FLOW_CTX.get()
            records, store = status.records, status.store
        except _FLOW_CTX.lookup_exc_cls:
            records, store = FlowRecords(), FlowStore()

        with _FLOW_CTX.unfold(FlowStatus(self, starts[0], True, completion, records, store)):
            try:
                if not self.graph._verified:
                    self.graph.verify()

                records.append(FlowRecord(RecordStage.FLOW_START, self.name, starts[0].name, event))

                idx = 0
                while idx < len(starts):
                    try:
                        await starts[idx].process(self, completion)
                        idx += 1
                    except FlowRewound:
                        pass

                records.append(
                    FlowRecord(RecordStage.FLOW_FINISH, self.name, starts[0].name, event)
                )

            except FlowBroke:
                pass

            except Exception as e:
                log_exc(
                    e,
                    msg=f"事件处理流 {self.name} 发生异常",
                    obj={
                        "event_id": event.id,
                        "event": event,
                        "completion": completion.__dict__,
                        "cur_flow": self,
                    },
                )

            finally:
                self._try_set_completed(completion)

    def _try_set_completed(self, completion: EventCompletion) -> None:
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
