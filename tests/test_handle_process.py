from melobot.handle.process import Flow, FlowNode
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
    assert sum(len(info.nexts) for info in nf.graph.values()) == 5
    assert len(nf.starts) == 3
    assert len(nf.ends) == 1
    nf = a.link(Flow("test"))
    assert sum(len(info.nexts) for info in nf.graph.values()) == 1
    assert len(nf.starts) == 3
    assert len(nf.ends) == 3
    nf = Flow("test").link(b)
    assert sum(len(info.nexts) for info in nf.graph.values()) == 1
    assert len(nf.starts) == 1
    assert len(nf.ends) == 1
    nf = Flow("test").link(c)
    assert sum(len(info.nexts) for info in nf.graph.values()) == 0
    assert len(nf.starts) == 1
    assert len(nf.ends) == 1
