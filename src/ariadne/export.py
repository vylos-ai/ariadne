"""Projection layer: render a process graph to a mermaid flowchart.

Per CLAUDE.md, diagrams are generated on demand from the graph -- never
stored as the primary artifact. This module only reads a ``GraphStore`` and
returns text; it never mutates the graph.

Only "process" content is rendered (``ProcessStep``/``Decision``/
``Exception``, connected by ``triggers``), grouped into per-``Role``
subgraphs via ``owned_by``, with ``System``/``DataObject`` nodes attached via
``requires``/``produces``. ``Evidence`` nodes and ``evidenced_by`` edges are
provenance, not process, and never appear in the diagram.
"""

from __future__ import annotations

import re

from ariadne.graph_store import GraphStore
from ariadne.schema import Edge, EdgeType, Node, NodeType

# Node types that make up the flowchart body (as opposed to attached
# System/DataObject nodes, or Role subgraph containers).
_PROCESS_NODE_TYPES = {NodeType.PROCESS_STEP, NodeType.DECISION, NodeType.EXCEPTION}

# Node types attached to process nodes via requires/produces, rendered with
# dashed arrows rather than as part of the main flow.
_ATTACHED_NODE_TYPES = {NodeType.SYSTEM, NodeType.DATA_OBJECT}

_INVALID_ID_CHARS = re.compile(r"[^A-Za-z0-9_]")


def _sanitize_id(node_id: str) -> str:
    """Derive a mermaid-safe node/subgraph id from a graph id."""
    sanitized = _INVALID_ID_CHARS.sub("_", node_id)
    if not sanitized or not (sanitized[0].isalpha() or sanitized[0] == "_"):
        sanitized = f"n_{sanitized}"
    return sanitized


def _sanitize_label(label: str) -> str:
    """Make a label safe to embed inside a double-quoted mermaid string."""
    flattened = label.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    without_quotes = flattened.replace('"', "'")
    return " ".join(without_quotes.split())


def _node_label(node: Node) -> str:
    value = node.properties.get("name") or node.properties.get("label") or node.id
    return _sanitize_label(str(value))


def _node_shape(node_id: str, label: str, node_type: NodeType) -> str:
    node_ref = _sanitize_id(node_id)
    quoted = f'"{label}"'
    if node_type == NodeType.DECISION:
        return f"{node_ref}{{{quoted}}}"
    if node_type == NodeType.EXCEPTION:
        return f"{node_ref}([{quoted}])"
    if node_type == NodeType.SYSTEM:
        return f"{node_ref}[[{quoted}]]"
    if node_type == NodeType.DATA_OBJECT:
        return f"{node_ref}[/{quoted}/]"
    return f"{node_ref}[{quoted}]"  # ProcessStep, default


def _process_nodes(store: GraphStore) -> list[Node]:
    nodes = [n for t in _PROCESS_NODE_TYPES for n in store.by_type(t)]
    return sorted(nodes, key=lambda n: n.id)


def _owner_by_node_id(store: GraphStore, process_ids: set[str]) -> dict[str, Node]:
    """Map each owned process node id to its (single, lowest-id) owning Role."""
    owned_by_edges = [
        e
        for e in store.by_type(EdgeType.OWNED_BY)
        if e.source in process_ids and store.get_node(e.target) is not None
    ]
    owner_ids: dict[str, list[str]] = {}
    for edge in owned_by_edges:
        owner_ids.setdefault(edge.source, []).append(edge.target)

    owners: dict[str, Node] = {}
    for node_id, role_ids in owner_ids.items():
        role_id = sorted(role_ids)[0]
        role = store.get_node(role_id)
        if role is not None:
            owners[node_id] = role
    return owners


def _attached_edges(store: GraphStore, process_ids: set[str]) -> list[Edge]:
    edges = [
        e
        for t in (EdgeType.REQUIRES, EdgeType.PRODUCES)
        for e in store.by_type(t)
        if e.source in process_ids
        and (target := store.get_node(e.target)) is not None
        and target.type in _ATTACHED_NODE_TYPES
    ]
    return sorted(edges, key=lambda e: (e.type.value, e.source, e.target))


def to_mermaid(store: GraphStore) -> str:
    """Render ``store`` as a deterministic mermaid ``flowchart TD`` string.

    Evidence nodes/edges are provenance, not process, and are never emitted.
    """
    lines = ["flowchart TD"]

    process_nodes = _process_nodes(store)
    process_ids = {n.id for n in process_nodes}
    owners = _owner_by_node_id(store, process_ids)

    # Group owned process nodes by role, one subgraph per role.
    nodes_by_role: dict[str, list[Node]] = {}
    for node in process_nodes:
        role = owners.get(node.id)
        if role is not None:
            nodes_by_role.setdefault(role.id, []).append(node)

    for role_id in sorted(nodes_by_role):
        role = store.get_node(role_id)
        role_label = _node_label(role)
        lines.append(f'  subgraph {_sanitize_id(role_id)}["{role_label}"]')
        for node in sorted(nodes_by_role[role_id], key=lambda n: n.id):
            lines.append(f"    {_node_shape(node.id, _node_label(node), node.type)}")
        lines.append("  end")

    # Process nodes with no owning role render ungrouped.
    for node in process_nodes:
        if node.id not in owners:
            lines.append(f"  {_node_shape(node.id, _node_label(node), node.type)}")

    # Attached System/DataObject nodes, declared once each, sorted by id.
    attached_edges = _attached_edges(store, process_ids)
    attached_ids = sorted({e.target for e in attached_edges})
    for node_id in attached_ids:
        node = store.get_node(node_id)
        if node is not None:
            lines.append(f"  {_node_shape(node.id, _node_label(node), node.type)}")

    # Main flow: triggers edges between process nodes, solid arrows.
    triggers_edges = sorted(
        (
            e
            for e in store.by_type(EdgeType.TRIGGERS)
            if e.source in process_ids and e.target in process_ids
        ),
        key=lambda e: (e.source, e.target),
    )
    for edge in triggers_edges:
        lines.append(f"  {_sanitize_id(edge.source)} --> {_sanitize_id(edge.target)}")

    # Attachments: requires/produces edges, dashed arrows.
    for edge in attached_edges:
        lines.append(f"  {_sanitize_id(edge.source)} -.-> {_sanitize_id(edge.target)}")

    return "\n".join(lines)
