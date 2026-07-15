"""Tests for the provenance validator: the trust-boundary gate described in
CLAUDE.md -- every edge and every non-trivial node property must trace back
to an ``Evidence`` node that actually exists in the graph.

``Edge.__post_init__`` already rejects a non-exempt edge with *no* evidence
ids at construction time, so these tests focus on what construction can't
catch: evidence references that don't resolve to any node, and evidence
references that resolve to a node that isn't an ``Evidence`` node.
"""

from pathlib import Path

from ariadne.graph_store import InMemoryGraphStore
from ariadne.schema import Edge, EdgeType, Node, NodeType
from ariadne.validation import validate

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "returned_order"
GOLD_GRAPH_PATH = FIXTURE_DIR / "gold_graph.json"


def _load_gold_store() -> InMemoryGraphStore:
    store = InMemoryGraphStore()
    store.load(GOLD_GRAPH_PATH)
    return store


def test_gold_graph_has_zero_violations():
    store = _load_gold_store()
    assert validate(store) == []


def test_dangling_node_evidence_reference_is_reported():
    store = InMemoryGraphStore()
    store.add_node(
        Node(
            id="step-a",
            type=NodeType.PROCESS_STEP,
            properties={"name": "Do the thing"},
            evidence_ids=["evidence-does-not-exist"],
        )
    )

    violations = validate(store)

    assert len(violations) == 1
    assert violations[0].subject == "step-a"
    assert "evidence-does-not-exist" in violations[0].message


def test_dangling_edge_evidence_reference_is_reported():
    store = InMemoryGraphStore()
    store.add_node(Node(id="step-a", type=NodeType.PROCESS_STEP))
    store.add_node(Node(id="step-b", type=NodeType.PROCESS_STEP))
    store.add_edge(
        Edge(
            type=EdgeType.TRIGGERS,
            source="step-a",
            target="step-b",
            evidence_ids=["evidence-does-not-exist"],
        )
    )

    violations = validate(store)

    assert len(violations) == 1
    assert "step-a" in violations[0].subject
    assert "step-b" in violations[0].subject
    assert "evidence-does-not-exist" in violations[0].message


def test_evidence_reference_pointing_at_non_evidence_node_is_reported():
    store = InMemoryGraphStore()
    store.add_node(Node(id="step-a", type=NodeType.PROCESS_STEP))
    store.add_node(Node(id="step-b", type=NodeType.PROCESS_STEP))
    store.add_edge(
        Edge(
            type=EdgeType.TRIGGERS,
            source="step-a",
            target="step-b",
            # step-b exists, but isn't an Evidence node.
            evidence_ids=["step-b"],
        )
    )

    violations = validate(store)

    assert len(violations) == 1
    assert "step-b" in violations[0].message
    assert "not an Evidence node" in violations[0].message


def test_evidenced_by_edge_with_no_evidence_ids_is_not_a_violation():
    store = InMemoryGraphStore()
    store.add_node(Node(id="step-a", type=NodeType.PROCESS_STEP))
    store.add_node(
        Node(id="evidence-a", type=NodeType.EVIDENCE, properties={"source": "x.txt"})
    )
    store.add_edge(
        Edge(type=EdgeType.EVIDENCED_BY, source="step-a", target="evidence-a")
    )

    assert validate(store) == []
