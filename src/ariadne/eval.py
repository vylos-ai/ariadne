"""Eval harness: precision/recall/F1 + evidence-grounding vs a gold graph.

Measures a candidate graph against the Phase 0 gold standard (or any
reference graph). Nodes are matched by ``(type, fuzzy-matched label)`` since
extraction can't be expected to reproduce gold node ids; edges are then
matched by ``(type, matched endpoints)`` using the node id mapping recovered
from that node match. See CLAUDE.md: this must exist before extraction
quality is measured, so regressions are caught early.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ariadne.graph_store import InMemoryGraphStore
from ariadne.labels import _labels_match, _node_label
from ariadne.schema import Edge, EdgeType, Node, NodeType


@dataclass
class PRF1:
    precision: float
    recall: float
    f1: float


@dataclass
class EvalReport:
    node_metrics: PRF1
    edge_metrics: PRF1
    grounding: float


def _all_nodes(store: InMemoryGraphStore) -> list[Node]:
    return [node for type_ in NodeType for node in store.by_type(type_)]


def _all_edges(store: InMemoryGraphStore) -> list[Edge]:
    return [edge for type_ in EdgeType for edge in store.by_type(type_)]


def _prf1(tp: int, fp: int, fn: int) -> PRF1:
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return PRF1(precision=precision, recall=recall, f1=f1)


def _match_nodes(
    candidate_nodes: list[Node], gold_nodes: list[Node]
) -> tuple[dict[str, str], int, int, int]:
    """Greedily match candidate nodes to gold nodes by (type, fuzzy label).

    Returns (candidate_id -> gold_id mapping, true positives, false
    positives, false negatives).
    """
    gold_by_type: dict[NodeType, list[Node]] = {}
    for node in gold_nodes:
        gold_by_type.setdefault(node.type, []).append(node)

    matched_gold_ids: set[str] = set()
    id_map: dict[str, str] = {}
    true_positives = 0

    for candidate in candidate_nodes:
        candidate_label = _node_label(candidate)
        match = next(
            (
                gold
                for gold in gold_by_type.get(candidate.type, [])
                if gold.id not in matched_gold_ids
                and _labels_match(candidate_label, _node_label(gold))
            ),
            None,
        )
        if match is not None:
            matched_gold_ids.add(match.id)
            id_map[candidate.id] = match.id
            true_positives += 1

    false_positives = len(candidate_nodes) - true_positives
    false_negatives = len(gold_nodes) - true_positives
    return id_map, true_positives, false_positives, false_negatives


def _match_edges(
    candidate_edges: list[Edge], gold_edges: list[Edge], id_map: dict[str, str]
) -> tuple[int, int, int]:
    """Match candidate edges to gold edges by (type, matched endpoints)."""
    remaining_gold = [(edge.type, edge.source, edge.target) for edge in gold_edges]
    true_positives = 0

    for edge in candidate_edges:
        key = (
            edge.type,
            id_map.get(edge.source, edge.source),
            id_map.get(edge.target, edge.target),
        )
        if key in remaining_gold:
            remaining_gold.remove(key)
            true_positives += 1

    false_positives = len(candidate_edges) - true_positives
    false_negatives = len(gold_edges) - true_positives
    return true_positives, false_positives, false_negatives


def grounding_coverage(store: InMemoryGraphStore) -> float:
    """Fraction of non-trivial node properties and edges backed by evidence.

    ``Evidence`` nodes and ``evidenced_by`` edges are themselves provenance
    links and are excluded from the denominator (see CLAUDE.md: provenance
    is first-class for everything that isn't provenance itself).
    """
    nodes = [
        node
        for node in _all_nodes(store)
        if node.type != NodeType.EVIDENCE and node.properties
    ]
    edges = [edge for edge in _all_edges(store) if edge.type != EdgeType.EVIDENCED_BY]

    total = len(nodes) + len(edges)
    if total == 0:
        return 1.0

    grounded = sum(1 for node in nodes if node.evidence_ids) + sum(
        1 for edge in edges if edge.evidence_ids
    )
    return grounded / total


def evaluate(candidate: InMemoryGraphStore, gold: InMemoryGraphStore) -> EvalReport:
    """Score ``candidate`` against ``gold``: node/edge P/R/F1 + grounding."""
    candidate_nodes = _all_nodes(candidate)
    gold_nodes = _all_nodes(gold)
    id_map, node_tp, node_fp, node_fn = _match_nodes(candidate_nodes, gold_nodes)
    node_metrics = _prf1(node_tp, node_fp, node_fn)

    candidate_edges = _all_edges(candidate)
    gold_edges = _all_edges(gold)
    edge_tp, edge_fp, edge_fn = _match_edges(candidate_edges, gold_edges, id_map)
    edge_metrics = _prf1(edge_tp, edge_fp, edge_fn)

    return EvalReport(
        node_metrics=node_metrics,
        edge_metrics=edge_metrics,
        grounding=grounding_coverage(candidate),
    )


def evaluate_paths(candidate_path: str | Path, gold_path: str | Path) -> EvalReport:
    """Load two graph JSON files and evaluate the first against the second."""
    candidate = InMemoryGraphStore()
    candidate.load(candidate_path)
    gold = InMemoryGraphStore()
    gold.load(gold_path)
    return evaluate(candidate, gold)


def format_report(report: EvalReport) -> str:
    """Human-readable rendering of an ``EvalReport``, for CLI output."""
    nm, em = report.node_metrics, report.edge_metrics
    return "\n".join(
        [
            f"Nodes:     P={nm.precision:.3f} R={nm.recall:.3f} F1={nm.f1:.3f}",
            f"Edges:     P={em.precision:.3f} R={em.recall:.3f} F1={em.f1:.3f}",
            f"Grounding: {report.grounding:.1%}",
        ]
    )
