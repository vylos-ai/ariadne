"""Graph store: the backend seam a future Kùzu (or other) backend slots into.

``GraphStore`` is the protocol every backend must satisfy. ``InMemoryGraphStore``
is the reference implementation used for Phase 0-1: it keeps nodes/edges in
memory and can persist them losslessly to/from a JSON file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, runtime_checkable

from ariadne.schema import (
    Edge,
    EdgeType,
    Node,
    NodeType,
    edge_from_dict,
    edge_to_dict,
    node_from_dict,
    node_to_dict,
)


@runtime_checkable
class GraphStore(Protocol):
    """Backend-agnostic interface for the process graph store."""

    def add_node(self, node: Node) -> None: ...

    def add_edge(self, edge: Edge) -> None: ...

    def get_node(self, node_id: str) -> Node | None: ...

    def neighbors(
        self, node_id: str, edge_type: EdgeType | None = None
    ) -> list[Edge]: ...

    def by_type(self, type_: NodeType | EdgeType) -> list[Node] | list[Edge]: ...

    def save(self, path: str | Path) -> None: ...

    def load(self, path: str | Path) -> None: ...


class InMemoryGraphStore:
    """In-memory reference implementation of ``GraphStore``, JSON-persisted."""

    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._edges: list[Edge] = []

    def add_node(self, node: Node) -> None:
        self._nodes[node.id] = node

    def add_edge(self, edge: Edge) -> None:
        if edge.source not in self._nodes:
            raise ValueError(
                f"cannot add edge: source node {edge.source!r} does not exist"
            )
        if edge.target not in self._nodes:
            raise ValueError(
                f"cannot add edge: target node {edge.target!r} does not exist"
            )
        self._edges.append(edge)

    def get_node(self, node_id: str) -> Node | None:
        return self._nodes.get(node_id)

    def neighbors(self, node_id: str, edge_type: EdgeType | None = None) -> list[Edge]:
        return [
            edge
            for edge in self._edges
            if node_id in (edge.source, edge.target)
            and (edge_type is None or edge.type == edge_type)
        ]

    def by_type(self, type_: NodeType | EdgeType) -> list[Node] | list[Edge]:
        if isinstance(type_, NodeType):
            return [node for node in self._nodes.values() if node.type == type_]
        return [edge for edge in self._edges if edge.type == type_]

    def save(self, path: str | Path) -> None:
        data = {
            "nodes": [node_to_dict(node) for node in self._nodes.values()],
            "edges": [edge_to_dict(edge) for edge in self._edges],
        }
        Path(path).write_text(json.dumps(data, indent=2))

    def load(self, path: str | Path) -> None:
        data = json.loads(Path(path).read_text())
        self._nodes = {n["id"]: node_from_dict(n) for n in data.get("nodes", [])}
        self._edges = [edge_from_dict(e) for e in data.get("edges", [])]
