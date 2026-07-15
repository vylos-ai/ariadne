"""Tests for the eval harness: node/edge P/R/F1 + evidence-grounding coverage."""

from pathlib import Path

from ariadne.eval import (
    evaluate,
    evaluate_paths,
    format_report,
    grounding_coverage,
)
from ariadne.graph_store import InMemoryGraphStore
from ariadne.schema import Edge, EdgeType, Node, NodeType

GOLD_GRAPH_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "returned_order"
    / "gold_graph.json"
)


def _step(node_id: str, name: str, evidence_ids: list[str] | None = None) -> Node:
    return Node(
        id=node_id,
        type=NodeType.PROCESS_STEP,
        properties={"name": name},
        evidence_ids=evidence_ids or ["evidence-1"],
    )


def _evidence(node_id: str) -> Node:
    return Node(id=node_id, type=NodeType.EVIDENCE, properties={"source": "doc.txt"})


def _triggers(source: str, target: str, evidence_ids: list[str] | None = None) -> Edge:
    return Edge(
        type=EdgeType.TRIGGERS,
        source=source,
        target=target,
        evidence_ids=evidence_ids or ["evidence-1"],
    )


def _gold_graph() -> InMemoryGraphStore:
    store = InMemoryGraphStore()
    store.add_node(_evidence("evidence-1"))
    store.add_node(_step("step-open-rma", "Open RMA"))
    store.add_node(_step("step-inspect", "Inspect returned item"))
    store.add_edge(_triggers("step-open-rma", "step-inspect"))
    return store


def test_node_pr_f1_perfect_match_on_exact_labels():
    gold = _gold_graph()
    candidate = _gold_graph()

    report = evaluate(candidate, gold)

    assert report.node_metrics.precision == 1.0
    assert report.node_metrics.recall == 1.0
    assert report.node_metrics.f1 == 1.0


def test_node_pr_f1_fuzzy_label_match():
    gold = _gold_graph()
    candidate = InMemoryGraphStore()
    candidate.add_node(_evidence("evidence-1"))
    # slightly different casing/whitespace -- should still fuzzy-match
    candidate.add_node(_step("cand-open-rma", "  open rma "))
    candidate.add_node(_step("cand-inspect", "Inspect returned item"))
    candidate.add_edge(_triggers("cand-open-rma", "cand-inspect"))

    report = evaluate(candidate, gold)

    assert report.node_metrics.precision == 1.0
    assert report.node_metrics.recall == 1.0


def test_node_pr_f1_penalizes_missing_and_extra_nodes():
    gold = _gold_graph()
    candidate = InMemoryGraphStore()
    candidate.add_node(_evidence("evidence-1"))
    # missing "Inspect returned item", plus one spurious extra node
    candidate.add_node(_step("cand-open-rma", "Open RMA"))
    candidate.add_node(_step("cand-extra", "Totally unrelated step"))

    report = evaluate(candidate, gold)

    # gold has 3 nodes (evidence + 2 steps); candidate matches evidence + 1 step = 2 tp
    # candidate has 3 nodes total -> fp = 1, gold has 3 -> fn = 1
    assert report.node_metrics.precision == 2 / 3
    assert report.node_metrics.recall == 2 / 3


def test_edge_pr_f1_matched_via_mapped_endpoints():
    gold = _gold_graph()
    candidate = InMemoryGraphStore()
    candidate.add_node(_evidence("evidence-1"))
    candidate.add_node(_step("cand-open-rma", "Open RMA"))
    candidate.add_node(_step("cand-inspect", "Inspect returned item"))
    candidate.add_edge(_triggers("cand-open-rma", "cand-inspect"))

    report = evaluate(candidate, gold)

    assert report.edge_metrics.precision == 1.0
    assert report.edge_metrics.recall == 1.0
    assert report.edge_metrics.f1 == 1.0


def test_edge_pr_f1_wrong_endpoint_is_a_false_positive():
    gold = _gold_graph()
    candidate = InMemoryGraphStore()
    candidate.add_node(_evidence("evidence-1"))
    candidate.add_node(_step("cand-open-rma", "Open RMA"))
    candidate.add_node(_step("cand-inspect", "Inspect returned item"))
    candidate.add_node(_step("cand-unrelated", "Unrelated step"))
    # wrong direction / wrong target -- doesn't correspond to any gold edge
    candidate.add_edge(_triggers("cand-open-rma", "cand-unrelated"))

    report = evaluate(candidate, gold)

    assert report.edge_metrics.precision == 0.0
    assert report.edge_metrics.recall == 0.0


def test_grounding_coverage_excludes_evidence_nodes_from_denominator():
    store = InMemoryGraphStore()
    store.add_node(_evidence("evidence-1"))
    store.add_node(_step("step-1", "Do the thing"))  # has evidence
    store.add_node(
        Node(id="step-2", type=NodeType.PROCESS_STEP, properties={"name": "Ungrounded"})
    )  # no evidence
    store.add_edge(_triggers("step-1", "step-2"))

    coverage = grounding_coverage(store)

    # denominator: step-1, step-2 (2 nontrivial nodes, Evidence excluded) + 1 edge = 3
    # grounded: step-1 (has evidence) + edge (has evidence) = 2; step-2 has none
    assert coverage == 2 / 3


def test_grounding_coverage_is_1_when_store_is_empty():
    assert grounding_coverage(InMemoryGraphStore()) == 1.0


def test_gold_graph_against_itself_is_perfect():
    """Sanity check: feeding the gold graph as its own candidate must score 1.0/1.0."""
    gold = InMemoryGraphStore()
    gold.load(GOLD_GRAPH_PATH)
    candidate = InMemoryGraphStore()
    candidate.load(GOLD_GRAPH_PATH)

    report = evaluate(candidate, gold)

    assert report.node_metrics.precision == 1.0
    assert report.node_metrics.recall == 1.0
    assert report.node_metrics.f1 == 1.0
    assert report.edge_metrics.precision == 1.0
    assert report.edge_metrics.recall == 1.0
    assert report.edge_metrics.f1 == 1.0
    assert report.grounding == 1.0


def test_evaluate_paths_loads_from_disk():
    report = evaluate_paths(GOLD_GRAPH_PATH, GOLD_GRAPH_PATH)

    assert report.node_metrics.f1 == 1.0
    assert report.edge_metrics.f1 == 1.0
    assert report.grounding == 1.0


def test_format_report_includes_all_metrics():
    gold = _gold_graph()
    report = evaluate(gold, gold)

    text = format_report(report)

    assert "Nodes" in text
    assert "Edges" in text
    assert "Grounding" in text
    assert "1.0" in text or "100" in text
