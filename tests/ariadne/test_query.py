"""Tests for the query/traversal layer (Phase 3): find/describe/walk/path/what_happens.

Run against the Phase 0 gold graph (returned-order process). Every returned
fact must carry the evidence ids grounding it -- see CLAUDE.md's trust
boundary -- and unknown ids / no-path cases must return empty results, never
raise.
"""

from pathlib import Path

from ariadne.graph_store import InMemoryGraphStore
from ariadne.query import describe, find_nodes, path, walk, what_happens
from ariadne.schema import EdgeType

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "returned_order"
GOLD_GRAPH_PATH = FIXTURE_DIR / "gold_graph.json"


def _gold_store() -> InMemoryGraphStore:
    store = InMemoryGraphStore()
    store.load(GOLD_GRAPH_PATH)
    return store


def test_find_nodes_ranks_best_match_first():
    store = _gold_store()

    results = find_nodes(store, "warehouse")

    assert results
    assert results[0].node.id == "role-warehouse"
    assert results[0].score > 0.5


def test_find_nodes_unrelated_text_returns_empty():
    store = _gold_store()

    results = find_nodes(store, "xyzzy nonsense query")

    assert results == []


def test_describe_returns_node_and_incident_edges_with_evidence():
    store = _gold_store()

    node, facts = describe(store, "step-inspect-item")

    assert node is not None
    assert node.id == "step-inspect-item"
    assert facts
    for fact in facts:
        assert fact.evidence_ids
        assert fact.neighbor_label

    owner_facts = [f for f in facts if f.edge.type == EdgeType.OWNED_BY]
    assert len(owner_facts) == 1
    assert owner_facts[0].neighbor.id == "role-warehouse"
    assert owner_facts[0].neighbor_label == "Warehouse"


def test_describe_unknown_node_returns_empty_result():
    store = _gold_store()

    node, facts = describe(store, "node-does-not-exist")

    assert node is None
    assert facts == []


def test_walk_out_direction_returns_only_outgoing_edges():
    store = _gold_store()

    facts = walk(store, "step-open-rma", direction="out")

    assert facts
    assert all(f.edge.source == "step-open-rma" for f in facts)
    assert all(f.evidence_ids for f in facts)
    neighbor_ids = {f.neighbor.id for f in facts}
    assert "step-send-label" in neighbor_ids
    assert "data-return-request" in neighbor_ids
    assert "role-support" in neighbor_ids


def test_walk_in_direction_returns_only_incoming_edges():
    store = _gold_store()

    facts = walk(store, "step-send-label", direction="in")

    assert len(facts) == 1
    assert facts[0].neighbor.id == "step-open-rma"
    assert facts[0].edge.type == EdgeType.TRIGGERS


def test_walk_filters_by_edge_type():
    store = _gold_store()

    facts = walk(store, "step-open-rma", edge_type=EdgeType.PRODUCES, direction="out")

    assert len(facts) == 1
    assert facts[0].neighbor.id == "data-return-request"


def test_walk_unknown_node_returns_empty():
    store = _gold_store()

    assert walk(store, "node-does-not-exist") == []


def test_path_finds_shortest_path_with_evidence():
    store = _gold_store()

    result = path(store, "step-open-rma", "step-process-refund")

    node_ids = [node.id for node in result.nodes]
    assert node_ids[0] == "step-open-rma"
    assert node_ids[-1] == "step-process-refund"
    assert len(result.edges) == len(result.nodes) - 1
    assert len(node_ids) > 1
    assert all(edge.evidence_ids for edge in result.edges)


def test_path_same_node_returns_single_node_no_edges():
    store = _gold_store()

    result = path(store, "step-open-rma", "step-open-rma")

    assert [node.id for node in result.nodes] == ["step-open-rma"]
    assert result.edges == []


def test_path_no_path_returns_empty():
    store = _gold_store()

    result = path(store, "step-open-rma", "node-does-not-exist")

    assert result.nodes == []
    assert result.edges == []


def test_what_happens_follows_triggers_and_produces_downstream():
    store = _gold_store()

    facts = what_happens(store, "step-open-rma")

    reached_ids = {f.neighbor.id for f in facts}
    assert "step-send-label" in reached_ids
    assert "step-inspect-item" in reached_ids
    assert "step-process-refund" in reached_ids
    assert "step-create-reship-order" in reached_ids
    assert "exception-manual-reship-handoff" in reached_ids
    # requires/owned_by edges are not part of the downstream trigger/produce
    # closure -- role-support (owned_by) should not be reached this way.
    assert "role-support" not in reached_ids
    assert all(f.evidence_ids for f in facts)


def test_what_happens_unknown_node_returns_empty():
    store = _gold_store()

    assert what_happens(store, "node-does-not-exist") == []
