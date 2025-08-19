from __future__ import annotations

from dataclasses import dataclass
from itertools import tee

from typing_extensions import Any, Generic, Hashable, Iterable, Iterator, Sequence, TypeIs, TypeVar

T = TypeVar("T", bound=Hashable)


@dataclass
class NodeInfo(Generic[T]):
    nexts: list[T]
    in_deg: int
    out_deg: int

    def copy(self) -> NodeInfo[T]:
        return NodeInfo(self.nexts, self.in_deg, self.out_deg)


def _is_iterable(obj: Any) -> TypeIs[Iterable]:
    # 这个操作实际上不是绝对安全，获取 iter 可能是有副作用的
    # 但是这种可能性非常非常小，所以不予考虑
    # 如果确实有相关反馈，那么再调整
    try:
        iter(obj)  # type: ignore[call-overload]
    except TypeError:
        return False
    else:
        return True


class DAGMapping(Generic[T]):
    def __init__(self, name: str, *edges: Iterable[Iterable[T] | T]) -> None:
        self.name = name
        self.map: dict[T, NodeInfo[T]] = {}
        self._verified = False

        _edges = tuple(
            tuple((elem,) if not _is_iterable(elem) else elem for elem in emap) for emap in edges
        )
        edge_pairs = self._get_edges(_edges)
        for n1, n2 in edge_pairs:
            self.add(n1, n2)
        self.verify()

    def __bool__(self) -> bool:
        return True

    def __len__(self) -> int:
        return len(self.map)

    def __getitem__(self, key: T) -> NodeInfo[T]:
        return self.map[key]

    def __contains__(self, key: T) -> bool:
        return key in self.map

    def __iter__(self) -> Iterator[tuple[T, NodeInfo[T]]]:
        return iter(self.map.items())

    @property
    def starts(self) -> tuple[T, ...]:
        return tuple(n for n, info in self.map.items() if info.in_deg == 0)

    @property
    def ends(self) -> tuple[T, ...]:
        return tuple(n for n, info in self.map.items() if info.out_deg == 0)

    def _get_edges(self, edge_maps: Sequence[Sequence[Iterable[T]]]) -> list[tuple[T, T]]:
        edges: list[tuple[T, T]] = []

        for emap in edge_maps:
            iter1, iter2 = tee(emap, 2)
            try:
                next(iter2)
            except StopIteration:
                continue
            if len(emap) == 1:
                for n in emap[0]:
                    self.add(n, None)
                continue

            for from_seq, to_seq in zip(iter1, iter2):
                for n1 in from_seq:
                    for n2 in to_seq:
                        if (n1, n2) not in edges:
                            edges.append((n1, n2))
        return edges

    def add(self, _from: T, to: T | None) -> None:
        from_info = self.map.setdefault(_from, NodeInfo([], 0, 0))
        if to is not None:
            to_info = self.map.setdefault(to, NodeInfo([], 0, 0))
            to_info.in_deg += 1
            from_info.out_deg += 1
            from_info.nexts.append(to)
        self._verified = False

    def verify(self) -> None:
        if self._verified:
            return

        graph = {n: info.copy() for n, info in self.map.items()}
        type_set = {type(n) for n in self.map}
        if len(type_set) > 1:
            type_dic: dict[type, list[Any]] = {}
            for n in self.map:
                type_dic.setdefault(type(n), []).append(n)
            raise TypeError(
                f"名为 {self.name} 的图结构中，结点类型不一致。"
                f"类型有：{type_set}。"
                f"每种类型的结点如下：{dict(sorted(type_dic.items(), key=lambda x: len(x[1])))}"
            )

        while len(graph):
            for n, info in graph.items():
                nexts, in_deg = info.nexts, info.in_deg
                if in_deg == 0:
                    graph.pop(n)
                    for next_n in nexts:
                        graph[next_n].in_deg -= 1
                    break
            else:
                raise ValueError(f"名为 {self.name} 的图结构中存在环路")
        self._verified = True

    def link(self, graph: DAGMapping[T], name: str) -> DAGMapping[T]:
        _froms = self.ends
        _tos = graph.starts
        new_edges = tuple((n1, n2) for n1 in _froms for n2 in _tos)
        new_graph = DAGMapping(name, *new_edges)

        for n1, info in (self.map | graph.map).items():
            if not len(info.nexts):
                new_graph.add(n1, None)
                continue
            for n2 in info.nexts:
                new_graph.add(n1, n2)

        new_graph.verify()
        return new_graph
