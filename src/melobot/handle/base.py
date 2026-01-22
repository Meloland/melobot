from __future__ import annotations

from asyncio import create_task, get_running_loop

from typing_extensions import Callable, Iterable, NoReturn

from ..adapter.base import Event
from ..ctx import BotCtx, EventCompletion, FlowCtx, FlowRecords
from ..ctx import FlowRecordStage as RecordStage
from ..ctx import FlowStatus, FlowStore
from ..di import DependNotMatched, inject_deps
from ..exceptions import FlowError
from ..log.report import log_exc
from ..typ.base import AsyncCallable, SyncOrAsyncCallable
from ..utils.base import to_async
from ..utils.common import get_obj_name
from .graph import DAGMapping

_FLOW_CTX = FlowCtx()


class FlowNode:
    """处理流结点"""

    def __init__(
        self,
        func: SyncOrAsyncCallable[..., bool | None],
        no_deps: bool = False,
        name: str | None = None,
    ) -> None:
        """初始化处理结点

        :param func: 处理结点的处理逻辑（函数）
        :param no_deps: 是否关闭内部的依赖注入支持
        :param name: 结点名称，为空时获取函数名作为结点名
        """
        if name is None:
            self.name = get_obj_name(func, otype="callable")
        else:
            self.name = name
        self.processor: AsyncCallable[..., bool | None] = (
            to_async(func) if no_deps else inject_deps(func, avoid_repeat=True)
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name})"

    async def process(
        self, flow: Flow, completion: EventCompletion, records: FlowRecords, store: FlowStore
    ) -> None:
        # 对于每个处理结点，运行时都需要新的状态，但是依然复用必要的信息
        status = FlowStatus(flow, self, completion, records, store)
        with _FLOW_CTX.unfold(status):
            try:
                records.add(RecordStage.NODE_START, status=status)
                try:
                    ret = await self.processor()
                    records.add(RecordStage.NODE_FINISH, status=status)
                except DependNotMatched as e:
                    ret = False
                    records.add(
                        RecordStage.DEPENDS_NOT_MATCH,
                        status=status,
                        prompt=f"Real({e.real_type}) <=> Annotation({e.hint})",
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
        :param edge_maps: 对应的 DAG 路径结构
        :param priority: 处理流的优先级
        :param guard: 守卫函数。在处理流运行前调用，返回 `True` 不再继续运行处理流。默认不启用
        """
        self.name = name
        self.graph = DAGMapping[FlowNode](name, *edge_maps)
        self.priority = priority

        self._active = True
        self._guard = to_async(guard) if guard is not None else None
        self._recordable = False

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

    async def _handle(self, event: Event) -> None:
        fut = get_running_loop().create_future()
        create_task(self._run(EventCompletion(event, fut, self)))
        await fut

    async def _run(
        self,
        completion: EventCompletion,
        records: FlowRecords | None = None,
        store: FlowStore | None = None,
    ) -> None:
        status = FlowStatus(self, None, completion, records, store)
        if self._guard is not None:
            try:
                with _FLOW_CTX.unfold(status):
                    if not await self._guard(completion.event):
                        return self._try_complete(completion)
            except Exception as e:
                log_exc(
                    e,
                    msg=f"事件处理流 {self.name} 守卫函数发生异常",
                    obj={
                        "event_id": completion.event.id,
                        "completion": completion.__dict__,
                        "guard": self._guard,
                    },
                )
                return self._try_complete(completion)

        starts = self.graph.starts
        if not len(starts):
            return self._try_complete(completion)
        try:
            self.graph.verify()
            status.records.add(RecordStage.FLOW_START, status=status)
            idx = 0
            while idx < len(starts):
                try:
                    await starts[idx].process(self, completion, status.records, status.store)
                    idx += 1
                except FlowRewound:
                    pass
            status.records.add(RecordStage.FLOW_FINISH, status=status)

        except FlowBroke:
            pass

        except Exception as e:
            log_exc(
                e,
                msg=f"事件处理流 {self.name} 发生异常",
                obj={
                    "event_id": completion.event.id,
                    "completion": completion.__dict__,
                    "cur_flow": self,
                },
            )

        finally:
            self._try_complete(completion)

    def _try_complete(self, completion: EventCompletion) -> None:
        if completion.creator is self:
            if not completion.ctrl_by_session and not completion.completed.done():
                completion.completed.set_result(None)
            completion.flow_ended = True

    def link(self, flow: Flow, priority: int | None = None, new_name: str | None = None) -> Flow:
        """连接另一处理流返回新处理流，并设置新优先级

        新处理流守卫函数为空，使用 :meth:`set_guard` 自行添加

        :param flow: 连接到末尾的流
        :param priority: 新优先级，若为空，则使用两者中较小的优先级
        :param new_name: 新处理流名称，为空时使用 `f"{flow1.name} ~ {flow2.name}"`
        :return: 新的处理流
        """
        name = f"{self.name} ~ {flow.name}" if new_name is None else new_name
        new_flow = Flow.from_graph(
            name,
            self.graph.link(flow.graph, name),
            priority=priority if priority else min(self.priority, flow.priority),
        )
        return new_flow

    def add(self, node: FlowNode) -> FlowNode:
        """添加结点的装饰器

        :param node: 添加的结点
        :return: 结点本身
        """
        self.graph.add(node, None)
        return node

    def start(self, node: FlowNode) -> FlowNode:
        """与 :meth:`add` 方法功能完全一致

        但此方法语义上更明确地表示添加的是起始结点。
        建议使用此方法装饰的结点，不要再添加前驱结点。

        :param node: 添加的结点
        :return: 结点本身
        """
        return self.add(node)

    def after(self, node: FlowNode) -> Callable[[FlowNode], FlowNode]:
        """在处理流某一参照结点后，添加新结点的装饰器函数

        :param node: 参照结点
        :return: 被装饰的结点
        """

        def after_wrapped(next_node: FlowNode) -> FlowNode:
            self.graph.add(node, next_node)
            return next_node

        return after_wrapped

    def before(self, node: FlowNode) -> Callable[[FlowNode], FlowNode]:
        """在处理流某一参照结点前，添加新结点的装饰器函数

        :param node: 参照结点
        :return: 被装饰的结点
        """

        def before_wrapped(pre_node: FlowNode) -> FlowNode:
            self.graph.add(pre_node, node)
            return pre_node

        return before_wrapped

    def merge(self, *nodes: FlowNode) -> Callable[[FlowNode], FlowNode]:
        """将处理流某几结点的控制流，在当前结点合并的装饰器函数

        :return: 被装饰的结点
        """

        def merge_wrapped(next_node: FlowNode) -> FlowNode:
            for node in nodes:
                self.graph.add(node, next_node)
            return next_node

        return merge_wrapped

    def fork(self, *nodes: FlowNode) -> Callable[[FlowNode], FlowNode]:
        """将处理流当前结点的控制流，分流到某几个结点的装饰器函数

        :return: 被装饰的结点
        """

        def fork_wrapped(pre_node: FlowNode) -> FlowNode:
            for node in nodes:
                self.graph.add(pre_node, node)
            return pre_node

        return fork_wrapped

    def enable_record(self) -> None:
        self._recordable = True


class _FlowSignal(BaseException): ...


class FlowBroke(_FlowSignal): ...


class FlowContinued(_FlowSignal): ...


class FlowRewound(_FlowSignal): ...


async def nextn() -> None:
    """运行下一处理结点（在处理流中使用）"""
    try:
        status = _FLOW_CTX.get()
    except _FLOW_CTX.lookup_exc_cls:
        raise FlowError("此时不在活动的事件处理流中，无法调用下一处理结点") from None

    n = status.node
    if n is None:
        raise FlowError("此时不在活动的处理结点中，无法调用下一处理结点")
    if not status.next_valid:
        return
    try:
        nexts = status.flow.graph[n].nexts
        idx = 0
        while idx < len(nexts):
            try:
                await nexts[idx].process(
                    status.flow, status.completion, status.records, status.store
                )
                idx += 1
            except FlowRewound:
                pass
    finally:
        status.next_valid = False


async def block() -> None:
    """阻止当前事件向更低优先级的处理流传播（在处理流中使用）"""
    status = _FLOW_CTX.get()
    status.records.add(RecordStage.BLOCK, status=status)
    status.completion.event.spread = False


async def stop() -> NoReturn:
    """立即停止当前处理流（在处理流中使用）"""
    status = _FLOW_CTX.get()
    status.records.add(
        RecordStage.STOP,
        RecordStage.NODE_EARLY_FINISH,
        RecordStage.FLOW_EARLY_FINISH,
        status=status,
    )
    raise FlowBroke("事件处理流被安全地提早结束，请无视这个内部工作信号")


async def bypass() -> NoReturn:
    """立即跳过当前处理结点剩下的步骤，运行下一处理结点（在处理流中使用）"""
    status = _FLOW_CTX.get()
    status.records.add(RecordStage.BYPASS, RecordStage.NODE_EARLY_FINISH, status=status)
    raise FlowContinued("事件处理流安全地跳过结点执行，请无视这个内部工作信号")


async def rewind() -> NoReturn:
    """立即重新运行当前处理结点（在处理流中使用）"""
    status = _FLOW_CTX.get()
    status.records.add(RecordStage.REWIND, status=status)
    raise FlowRewound("事件处理流安全地重复执行处理结点，请无视这个内部工作信号")


async def flow_to(flow: Flow, share_store: bool = False) -> None:
    """立即进入一个其他处理流（在处理流中使用）"""
    status = _FLOW_CTX.get()
    if flow is status.flow:
        raise FlowError("无法在处理流中进入自身处理流")
    await flow._run(status.completion.copy(), status.records, status.store if share_store else None)
