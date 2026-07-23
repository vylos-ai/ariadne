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

from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel

from ariadne.graph_store import InMemoryGraphStore
from ariadne.labels import _FUZZY_MATCH_THRESHOLD, _label_similarity, _node_label
from ariadne.llm import build_model
from ariadne.schema import Edge, EdgeType, Node, NodeType

# Below this similarity, two labels are considered clearly distinct and are
# never merged, never sent to an adjudicator. Between this floor and
# ``_FUZZY_MATCH_THRESHOLD`` is the "ambiguity band": rule-based matching
# can't decide, so an adjudicator (if supplied) is consulted; without one,
# the conservative default is to leave the pair unmerged (a wrong merge is
# worse than a missed one -- see CLAUDE.md provenance/trust discussion).
AMBIGUITY_FLOOR = 0.55


class ResolutionAdjudicator(Protocol):
    """Anything that can decide whether two ambiguous nodes are the same
    entity, given their type, labels, properties, and evidence ids."""

    def same_entity(self, node_a: Node, node_b: Node) -> bool: ...


@dataclass
class FakeAdjudicator:
    """Offline stand-in for tests: canned verdicts, no network calls.

    ``affirm`` is a set of ``frozenset({id_a, id_b})`` pairs the adjudicator
    should confirm as the same entity. Every other pair is denied.
    """

    affirm: set[frozenset]

    def same_entity(self, node_a: Node, node_b: Node) -> bool:
        return frozenset({node_a.id, node_b.id}) in self.affirm


def _describe_node(node: Node) -> str:
    return (
        f"type={node.type.value}, label={_node_label(node)!r}, "
        f"properties={node.properties!r}, evidence_ids={node.evidence_ids!r}"
    )


class SameEntityVerdict(BaseModel):
    """Structured verdict from the adjudicator agent."""

    same_entity: bool = Field(
        description="True if the two nodes are the same real-world entity."
    )
    reason: str = Field(description="Brief justification for the verdict.")


_INSTRUCTIONS = (
    "Decide whether two candidate process-graph nodes refer to the same "
    "real-world entity (e.g. the same team, system, or step described two "
    "different ways). Respond with a structured verdict."
)


class PydanticAIAdjudicator:
    """Real adjudicator: wraps a Pydantic AI ``Agent`` behind
    ``ResolutionAdjudicator``.

    Provider-agnostic -- the underlying model is whatever ``build_model()``
    (see ``ariadne.llm``) resolves from configuration. Structured output is
    enforced by pydantic (``SameEntityVerdict``); a Pydantic AI test double
    (``TestModel``/``FunctionModel``) can be passed directly as ``model=``
    in tests to guarantee no live API calls are made.
    """

    def __init__(self, model: str | OpenAIChatModel | None = None) -> None:
        self.agent = Agent(
            model if model is not None else build_model(),
            output_type=SameEntityVerdict,
            instructions=_INSTRUCTIONS,
        )

    def same_entity(self, node_a: Node, node_b: Node) -> bool:
        prompt = (
            "Do these two process-graph nodes refer to the same real-world "
            "entity?\n\n"
            f"Node A: {_describe_node(node_a)}\n"
            f"Node B: {_describe_node(node_b)}"
        )
        result = self.agent.run_sync(prompt)
        return result.output.same_entity


def _all_nodes(store: InMemoryGraphStore) -> list[Node]:
    return [node for type_ in NodeType for node in store.by_type(type_)]


def _all_edges(store: InMemoryGraphStore) -> list[Edge]:
    return [edge for type_ in EdgeType for edge in store.by_type(type_)]


def _should_merge(
    node_a: Node,
    node_b: Node,
    adjudicator: ResolutionAdjudicator | None,
) -> bool:
    similarity = _label_similarity(_node_label(node_a), _node_label(node_b))
    if similarity >= _FUZZY_MATCH_THRESHOLD:
        return True
    if similarity < AMBIGUITY_FLOOR:
        return False
    if adjudicator is None:
        return False
    return adjudicator.same_entity(node_a, node_b)


def _cluster_nodes(
    nodes: list[Node], adjudicator: ResolutionAdjudicator | None = None
) -> list[list[Node]]:
    """Union-find clustering: same NodeType (never Evidence) + fuzzy label
    match (or an adjudicator verdict for ambiguous-band pairs), transitively
    (a~b, b~c => one cluster)."""
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
            if node_b.type == node_a.type and _should_merge(
                node_a, node_b, adjudicator
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


def resolve(
    store: InMemoryGraphStore,
    adjudicator: ResolutionAdjudicator | None = None,
) -> InMemoryGraphStore:
    """Collapse duplicate/near-duplicate nodes into canonical nodes.

    Pure function: returns a new store, does not mutate ``store``. Pairs
    scoring in the "ambiguity band" (see ``AMBIGUITY_FLOOR``) are only
    merged if ``adjudicator`` confirms them; without one, ambiguous pairs
    are conservatively left unmerged.
    """
    nodes = _all_nodes(store)
    clusters = _cluster_nodes(nodes, adjudicator)

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
