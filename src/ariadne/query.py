"""Query/traversal layer: the small set of graph questions an agent asks.

Every answer is grounded -- each returned fact carries the ``evidence_ids``
of the edge that produced it (see CLAUDE.md: an ungrounded answer violates
the trust boundary). Unknown node ids and no-path cases return empty
results rather than raising, so a calling agent can treat "not found" as
data, not an error to handle.

Vector search is deliberately out of scope (YAGNI) -- ``find_nodes`` uses
the same fuzzy label matching already used by the eval harness.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from difflib import SequenceMatcher

from ariadne.eval import _all_edges, _all_nodes, _node_label
from ariadne.graph_store import GraphStore
from ariadne.schema import Edge, EdgeType, Node

# Below this fuzzy-match score, a candidate is considered noise and dropped
# from find_nodes results.
_FIND_SCORE_THRESHOLD = 0.5

# Edge types followed by what_happens' downstream closure, in the
# source -> target direction ("what does X lead to").
_DOWNSTREAM_EDGE_TYPES = {EdgeType.TRIGGERS, EdgeType.PRODUCES}


@dataclass
class ScoredNode:
    node: Node
    score: float


@dataclass
class NeighborFact:
    """One edge incident to a node, resolved with the neighbor node."""

    edge: Edge
    neighbor: Node
    direction: str  # "out" (node is source) or "in" (node is target)

    @property
    def neighbor_label(self) -> str:
        return _node_label(self.neighbor)

    @property
    def evidence_ids(self) -> list[str]:
        return self.edge.evidence_ids


@dataclass
class PathResult:
    nodes: list[Node]
    edges: list[Edge]


def _match_score(text: str, label: str) -> float:
    a, b = text.strip().lower(), label.strip().lower()
    if not a or not b:
        return 0.0
    ratio = SequenceMatcher(None, a, b).ratio()
    if a in b or b in a:
        ratio = max(ratio, 0.9)
    return ratio


def find_nodes(store: GraphStore, text: str) -> list[ScoredNode]:
    """Fuzzy label lookup, ranked best-match first."""
    scored = [
        ScoredNode(node=node, score=_match_score(text, _node_label(node)))
        for node in _all_nodes(store)
    ]
    scored = [s for s in scored if s.score >= _FIND_SCORE_THRESHOLD]
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored


def _neighbor_facts(
    store: GraphStore,
    node_id: str,
    edge_type: EdgeType | None,
    direction: str,
) -> list[NeighborFact]:
    facts = []
    for edge in store.neighbors(node_id, edge_type=edge_type):
        is_out = edge.source == node_id
        if direction == "out" and not is_out:
            continue
        if direction == "in" and is_out:
            continue
        neighbor_id = edge.target if is_out else edge.source
        neighbor = store.get_node(neighbor_id)
        if neighbor is None:
            continue
        facts.append(
            NeighborFact(
                edge=edge, neighbor=neighbor, direction="out" if is_out else "in"
            )
        )
    return facts


def describe(store: GraphStore, node_id: str) -> tuple[Node | None, list[NeighborFact]]:
    """The node plus every incident edge, each resolved with its neighbor.

    Unknown node ids return ``(None, [])`` -- the same empty-result shape
    every other query function uses for a not-found case, never an
    exception or a bare ``None`` sentinel.
    """
    node = store.get_node(node_id)
    if node is None:
        return None, []
    return node, _neighbor_facts(store, node_id, edge_type=None, direction="both")


def walk(
    store: GraphStore,
    node_id: str,
    edge_type: EdgeType | None = None,
    direction: str = "both",
) -> list[NeighborFact]:
    """One-hop neighbors of ``node_id``, optionally filtered by edge type/direction."""
    if store.get_node(node_id) is None:
        return []
    return _neighbor_facts(store, node_id, edge_type=edge_type, direction=direction)


def path(store: GraphStore, from_id: str, to_id: str) -> PathResult:
    """Shortest path between two nodes, treating edges as traversable both ways."""
    if store.get_node(from_id) is None or store.get_node(to_id) is None:
        return PathResult(nodes=[], edges=[])
    if from_id == to_id:
        return PathResult(nodes=[store.get_node(from_id)], edges=[])

    # BFS over all edges, undirected: each step remembers the edge taken.
    queue: deque[str] = deque([from_id])
    came_from: dict[str, tuple[str, Edge]] = {}
    visited = {from_id}

    while queue:
        current = queue.popleft()
        if current == to_id:
            break
        for edge in store.neighbors(current):
            neighbor_id = edge.target if edge.source == current else edge.source
            if neighbor_id in visited:
                continue
            visited.add(neighbor_id)
            came_from[neighbor_id] = (current, edge)
            queue.append(neighbor_id)

    if to_id not in came_from:
        return PathResult(nodes=[], edges=[])

    node_ids = [to_id]
    edges: list[Edge] = []
    current = to_id
    while current != from_id:
        previous, edge = came_from[current]
        edges.append(edge)
        node_ids.append(previous)
        current = previous
    node_ids.reverse()
    edges.reverse()

    nodes = [store.get_node(nid) for nid in node_ids]
    return PathResult(nodes=nodes, edges=edges)


def what_happens(store: GraphStore, node_id: str) -> list[NeighborFact]:
    """Downstream closure over ``triggers``/``produces`` edges from ``node_id``."""
    if store.get_node(node_id) is None:
        return []

    reached: list[NeighborFact] = []
    visited = {node_id}
    queue: deque[str] = deque([node_id])

    while queue:
        current = queue.popleft()
        for edge in _all_edges(store):
            if edge.source != current or edge.type not in _DOWNSTREAM_EDGE_TYPES:
                continue
            if edge.target in visited:
                continue
            neighbor = store.get_node(edge.target)
            if neighbor is None:
                continue
            visited.add(edge.target)
            reached.append(NeighborFact(edge=edge, neighbor=neighbor, direction="out"))
            queue.append(edge.target)

    return reached
