"""Entity resolution: collapse duplicate/near-duplicate nodes into canonical
nodes. See CLAUDE.md Phase 2 -- "This is the hardest and most important
step -- expect to spend disproportionate effort here."

``resolve()`` is pure: it returns a new ``InMemoryGraphStore`` and never
mutates the input. Nodes are clustered transitively by (same ``NodeType`` +
fuzzy label match); ``Evidence`` nodes are never merged, since each one is a
distinct provenance record even if its text happens to coincide with
another's.
"""

from __future__ import annotations

from ariadne.graph_store import InMemoryGraphStore
from ariadne.labels import _labels_match, _node_label
from ariadne.schema import Edge, EdgeType, Node, NodeType


def _all_nodes(store: InMemoryGraphStore) -> list[Node]:
    return [node for type_ in NodeType for node in store.by_type(type_)]


def _all_edges(store: InMemoryGraphStore) -> list[Edge]:
    return [edge for type_ in EdgeType for edge in store.by_type(type_)]


def _cluster_nodes(nodes: list[Node]) -> list[list[Node]]:
    """Union-find clustering: same NodeType (never Evidence) + fuzzy label
    match, transitively (a~b, b~c => one cluster)."""
    parent = {node.id: node.id for node in nodes}

    def find(node_id: str) -> str:
        while parent[node_id] != node_id:
            parent[node_id] = parent[parent[node_id]]
            node_id = parent[node_id]
        return node_id

    def union(a: str, b: str) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_a] = root_b

    for i, node_a in enumerate(nodes):
        if node_a.type == NodeType.EVIDENCE:
            continue
        for node_b in nodes[i + 1 :]:
            if node_b.type == node_a.type and _labels_match(
                _node_label(node_a), _node_label(node_b)
            ):
                union(node_a.id, node_b.id)

    clusters: dict[str, list[Node]] = {}
    for node in nodes:
        clusters.setdefault(find(node.id), []).append(node)
    return list(clusters.values())


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _merge_properties(members: list[Node]) -> dict:
    """First non-empty value per key wins, iterating cluster members in
    sorted-id order for determinism. Losing distinct labels are recorded in
    ``properties["aliases"]``."""
    sorted_members = sorted(members, key=lambda node: node.id)
    merged: dict = {}
    labels_seen: list[str] = []
    for node in sorted_members:
        label = _node_label(node)
        if label and label not in labels_seen:
            labels_seen.append(label)
        for key, value in node.properties.items():
            if value and key not in merged:
                merged[key] = value
    if len(labels_seen) > 1:
        merged["aliases"] = labels_seen[1:]
    return merged


def _merge_cluster(cluster: list[Node], id_map: dict[str, str]) -> Node:
    canonical_id = min(node.id for node in cluster)
    sorted_members = sorted(cluster, key=lambda node: node.id)
    evidence_ids = _dedupe_preserve_order(
        [
            id_map.get(evidence_id, evidence_id)
            for member in sorted_members
            for evidence_id in member.evidence_ids
        ]
    )
    return Node(
        id=canonical_id,
        type=cluster[0].type,
        properties=_merge_properties(cluster),
        evidence_ids=evidence_ids,
    )


def resolve(store: InMemoryGraphStore) -> InMemoryGraphStore:
    """Collapse duplicate/near-duplicate nodes into canonical nodes.

    Pure function: returns a new store, does not mutate ``store``.
    """
    nodes = _all_nodes(store)
    clusters = _cluster_nodes(nodes)

    id_map: dict[str, str] = {}
    for cluster in clusters:
        canonical_id = min(node.id for node in cluster)
        for node in cluster:
            id_map[node.id] = canonical_id

    resolved = InMemoryGraphStore()
    merged_nodes = sorted(
        (_merge_cluster(cluster, id_map) for cluster in clusters),
        key=lambda node: node.id,
    )
    for node in merged_nodes:
        resolved.add_node(node)

    merged_edges: dict[tuple[EdgeType, str, str], list[str]] = {}
    for edge in _all_edges(store):
        new_source = id_map.get(edge.source, edge.source)
        new_target = id_map.get(edge.target, edge.target)
        new_evidence = [id_map.get(eid, eid) for eid in edge.evidence_ids]
        key = (edge.type, new_source, new_target)
        merged_edges[key] = _dedupe_preserve_order(
            merged_edges.get(key, []) + new_evidence
        )

    for (edge_type, source, target), evidence_ids in sorted(
        merged_edges.items(),
        key=lambda item: (item[0][0].value, item[0][1], item[0][2]),
    ):
        resolved.add_edge(
            Edge(
                type=edge_type,
                source=source,
                target=target,
                evidence_ids=evidence_ids,
            )
        )

    return resolved
