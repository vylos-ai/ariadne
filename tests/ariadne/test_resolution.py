"""Tests for entity resolution: collapsing duplicate/near-duplicate nodes.

See CLAUDE.md Phase 2: entity resolution is "where most of the engineering
effort should go." ``resolve()`` is a pure function -- it must not mutate the
input store, and given the same input it must produce byte-identical output.
"""

from ariadne.graph_store import InMemoryGraphStore
from ariadne.resolution import resolve
from ariadne.schema import Edge, EdgeType, Node, NodeType
from ariadne.validation import validate


def _step(node_id: str, name: str, evidence_ids: list[str] | None = None) -> Node:
    return Node(
        id=node_id,
        type=NodeType.PROCESS_STEP,
        properties={"name": name},
        evidence_ids=evidence_ids or [],
    )


def _evidence(node_id: str, source: str = "doc.txt") -> Node:
    return Node(id=node_id, type=NodeType.EVIDENCE, properties={"source": source})


def test_resolve_merges_nodes_with_fuzzy_matching_labels():
    store = InMemoryGraphStore()
    store.add_node(_step("z-step", "  open rma "))
    store.add_node(_step("a-step", "Open RMA"))

    resolved = resolve(store)

    process_steps = resolved.by_type(NodeType.PROCESS_STEP)
    assert len(process_steps) == 1
    assert process_steps[0].id == "a-step"


def test_resolve_does_not_merge_across_different_node_types():
    store = InMemoryGraphStore()
    store.add_node(_step("step-1", "Widget"))
    store.add_node(
        Node(id="sys-1", type=NodeType.SYSTEM, properties={"name": "Widget"})
    )

    resolved = resolve(store)

    assert len(resolved.by_type(NodeType.PROCESS_STEP)) == 1
    assert len(resolved.by_type(NodeType.SYSTEM)) == 1


def test_resolve_never_merges_evidence_nodes():
    store = InMemoryGraphStore()
    store.add_node(_evidence("ev-1", "same text"))
    store.add_node(_evidence("ev-2", "same text"))

    resolved = resolve(store)

    assert len(resolved.by_type(NodeType.EVIDENCE)) == 2


def test_resolve_unions_evidence_ids_deduped_preserving_order():
    store = InMemoryGraphStore()
    store.add_node(_step("a-step", "Open RMA", evidence_ids=["ev-1", "ev-2"]))
    store.add_node(_step("b-step", "open rma", evidence_ids=["ev-2", "ev-3"]))

    resolved = resolve(store)

    merged = resolved.get_node("a-step")
    assert merged.evidence_ids == ["ev-1", "ev-2", "ev-3"]


def test_resolve_merges_properties_first_non_empty_wins_and_records_aliases():
    store = InMemoryGraphStore()
    store.add_node(
        Node(
            id="b-step",
            type=NodeType.PROCESS_STEP,
            properties={"name": "open rma", "owner": "Alice"},
        )
    )
    store.add_node(
        Node(id="a-step", type=NodeType.PROCESS_STEP, properties={"name": "Open RMA"})
    )

    resolved = resolve(store)

    merged = resolved.get_node("a-step")
    assert merged.properties["name"] == "Open RMA"
    assert merged.properties["owner"] == "Alice"
    assert merged.properties["aliases"] == ["open rma"]


def test_resolve_rewrites_edges_to_canonical_ids_and_dedupes():
    store = InMemoryGraphStore()
    store.add_node(_step("a-step", "Open RMA"))
    store.add_node(_step("b-step", "open rma"))
    store.add_node(_step("c-step", "Inspect"))
    store.add_edge(
        Edge(
            type=EdgeType.TRIGGERS,
            source="a-step",
            target="c-step",
            evidence_ids=["ev-1"],
        )
    )
    store.add_edge(
        Edge(
            type=EdgeType.TRIGGERS,
            source="b-step",
            target="c-step",
            evidence_ids=["ev-2"],
        )
    )

    resolved = resolve(store)

    edges = resolved.by_type(EdgeType.TRIGGERS)
    assert len(edges) == 1
    edge = edges[0]
    assert edge.source == "a-step"
    assert edge.target == "c-step"
    assert edge.evidence_ids == ["ev-1", "ev-2"]


def test_resolve_does_not_mutate_input_store():
    store = InMemoryGraphStore()
    store.add_node(_step("a-step", "Open RMA"))
    store.add_node(_step("b-step", "open rma"))

    resolve(store)

    assert len(store.by_type(NodeType.PROCESS_STEP)) == 2


def test_resolve_is_deterministic(tmp_path):
    store = InMemoryGraphStore()
    store.add_node(_step("b-step", "open rma", evidence_ids=["ev-1"]))
    store.add_node(_step("a-step", "Open RMA", evidence_ids=["ev-2"]))
    store.add_node(_step("c-step", "Inspect", evidence_ids=["ev-1"]))
    store.add_edge(
        Edge(
            type=EdgeType.TRIGGERS,
            source="b-step",
            target="c-step",
            evidence_ids=["ev-1"],
        )
    )
    store.add_edge(
        Edge(
            type=EdgeType.TRIGGERS,
            source="a-step",
            target="c-step",
            evidence_ids=["ev-2"],
        )
    )

    path1 = tmp_path / "one.json"
    path2 = tmp_path / "two.json"
    resolve(store).save(path1)
    resolve(store).save(path2)

    assert path1.read_text() == path2.read_text()


def test_resolve_output_passes_validation():
    store = InMemoryGraphStore()
    store.add_node(_evidence("evidence-1"))
    store.add_node(_step("a-step", "Open RMA", evidence_ids=["evidence-1"]))
    store.add_node(_step("b-step", "open rma", evidence_ids=["evidence-1"]))
    store.add_node(_step("c-step", "Inspect", evidence_ids=["evidence-1"]))
    store.add_edge(
        Edge(
            type=EdgeType.TRIGGERS,
            source="a-step",
            target="c-step",
            evidence_ids=["evidence-1"],
        )
    )
    store.add_edge(
        Edge(
            type=EdgeType.TRIGGERS,
            source="b-step",
            target="c-step",
            evidence_ids=["evidence-1"],
        )
    )

    resolved = resolve(store)

    assert validate(resolved) == []
