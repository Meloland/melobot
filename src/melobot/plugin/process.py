from __future__ import annotations

from contextvars import ContextVar

from ..adapter.base import Event
from ..context.session import BotSession
from ..exceptions import FlowBroke, FlowContinued, FlowRewound, ProcessFlowError
from ..typing import AsyncCallable

_NODE_LOCAL: ContextVar[ProcessNode] = ContextVar("_NODE_LOCAL")
FLOW_RECORD: ContextVar[list[str]] = ContextVar("FLOW_RECORD")


async def next() -> None:
    try:
        node = _NODE_LOCAL.get()
        idx = 0
        while idx < len(node.nexts):
            try:
                await node.nexts[idx].process()
                idx += 1
            except FlowRewound:
                pass
    except LookupError:
        raise ProcessFlowError("此刻不在活动的处理流中，无法调用下一处理结点")


async def block() -> None:
    BotSession.current_event()._spread = False


async def exit() -> None:
    FLOW_RECORD.get().append(f"{_NODE_LOCAL.get().name} -> [EXIT]")
    raise FlowBroke("事件处理流被安全地提早结束，请无视这个内部工作信号")


async def bypass() -> None:
    FLOW_RECORD.get().append(f"{_NODE_LOCAL.get().name} -> [BYPASS] Out")
    raise FlowContinued("事件处理流安全地跳过结点执行，请无视这个内部工作信号")


async def rewind() -> None:
    FLOW_RECORD.get().append(f"{_NODE_LOCAL.get().name} -> [REWIND]")
    raise FlowRewound("事件处理流安全地重复执行处理结点，请无视这个内部工作信号")


class ProcessNode:
    def __init__(self, etype: type[Event], name: str = "") -> None:
        self.name = name
        self.etype = etype
        self.nexts: list[ProcessNode] = []
        self.depth: int = 1
        self.processor: AsyncCallable[..., None]

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, etype={self.etype})"

    def pretty_str(self) -> str:
        indent = "\n" + self.depth * "    "
        nexts = indent.join(n.pretty_str() for n in self.nexts)
        if len(self.nexts):
            nexts = f"{indent}{nexts}{indent[:-4]}"
        return f"{self.__class__.__name__}(name={self.name}, etype={self.etype}, nexts=[{nexts}])"

    def __call__(self, func: AsyncCallable[..., None]) -> ProcessNode:
        self.processor = func
        if self.name == "":
            self.name = func.__name__
        return self

    async def process(self) -> None:
        # TODO: 完成依赖注入操作
        if not isinstance(BotSession.current_event(), self.etype):
            FLOW_RECORD.get().append(f"Check Failed and Not Into -x-> {self.name}")
            return

        try:
            node_token = _NODE_LOCAL.set(self)
            FLOW_RECORD.get().append(f"Checked and Into -> {self.name}")
            await self.processor()
            FLOW_RECORD.get().append(f"{self.name} -> Normal Out")
        except FlowContinued:
            await next()
        finally:
            _NODE_LOCAL.reset(node_token)


class ProcessFlow:
    def __init__(self, *starts: ProcessNode, name: str = "") -> None:
        self.name = name
        self.starts = starts
        self._sets: set[ProcessNode] = set(starts)

        if len(starts) > 1 and len(self._sets) != len(starts):
            raise ProcessFlowError("DAG 初始化时存在重复节点")

    def __repr__(self) -> str:
        output = f"{self.__class__.__name__}(nums={len(self._sets)}"
        if len(self._sets):
            output += f", starts=[{', '.join(repr(n) for n in self.starts)}])"
        else:
            output += ")"
        return output

    def pretty_str(self) -> str:
        string = []
        for n in self.starts:
            string.extend(n.pretty_str().split("\n"))
        starts = "\n".join(map(lambda s: "    " + s, string))
        if len(self.starts):
            starts = f"\n{starts}\n"
        return f"{self.__class__.__name__}(name={self.name}, nums={len(self._sets)}, starts=[{starts}])"

    def __rshift__(self, other: ProcessNode | ProcessFlow) -> ProcessFlow:
        if isinstance(other, ProcessNode):
            other = ProcessFlow(other)

        if not len(self.starts):
            self.starts = other.starts
            self._sets = other._sets
            return other

        for n_node in other.starts:
            if n_node in self._sets:
                raise ProcessFlowError(
                    f"处理流构建时结点 {n_node.name} 出现了多次，这将形成环路"
                )

            for node in self.starts:
                node.nexts.append(n_node)
            n_node.depth = node.depth + 1
            self._sets.add(n_node)
            other._sets = self._sets
        return other

    async def run(self) -> None:
        try:
            record_token = FLOW_RECORD.set([])

            idx = 0
            while idx < len(self.starts):
                try:
                    await self.starts[idx].process()
                    idx += 1
                except FlowRewound:
                    pass

        except FlowBroke:
            pass
        finally:
            FLOW_RECORD.reset(record_token)
