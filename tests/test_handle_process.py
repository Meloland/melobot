from melobot.handle.base import Flow, FlowNode
from tests.base import *


def node():
    async def node():
        return True

    n = FlowNode(node)
    n.name = str(id(n))
    return n


async def test_flow_link():
    a = Flow("a", [node()], [node(), node()], [node()])
    b = Flow("b", [node(), node()])
    c = Flow("c", [node()])
    nf = a.link(b)
    assert sum(len(info.nexts) for _, info in nf.graph) == 5
    assert len(nf.graph.starts) == 3
    assert len(nf.graph.ends) == 1
    nf = a.link(Flow("test"))
    assert sum(len(info.nexts) for _, info in nf.graph) == 1
    assert len(nf.graph.starts) == 3
    assert len(nf.graph.ends) == 3
    nf = Flow("test").link(b)
    assert sum(len(info.nexts) for _, info in nf.graph) == 1
    assert len(nf.graph.starts) == 1
    assert len(nf.graph.ends) == 1
    nf = Flow("test").link(c)
    assert sum(len(info.nexts) for _, info in nf.graph) == 0
    assert len(nf.graph.starts) == 1
    assert len(nf.graph.ends) == 1
