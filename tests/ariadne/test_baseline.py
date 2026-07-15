"""Phase 1 baseline: extract -> validate -> eval, tied together end-to-end.

Runs the offline recorded-payload extraction pipeline over the Phase 0
source documents, checks the result passes provenance validation, evals it
against the gold graph, and asserts the recorded P/R/F1 baseline hasn't
regressed.
"""

from __future__ import annotations

import json
from pathlib import Path

from ariadne.baseline import evaluate_baseline
from ariadne.schema import NodeType

BASELINE_METRICS_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "returned_order"
    / "baseline_metrics.json"
)


def _load_committed_baseline() -> dict:
    return json.loads(BASELINE_METRICS_PATH.read_text())


def test_baseline_graph_passes_provenance_validation(tmp_path):
    result = evaluate_baseline(tmp_path / "baseline_out")

    assert result.violations == []


def test_baseline_graph_is_nonempty(tmp_path):
    result = evaluate_baseline(tmp_path / "baseline_out")

    assert result.graph.by_type(NodeType.PROCESS_STEP)


def test_baseline_run_is_deterministic(tmp_path):
    result_a = evaluate_baseline(tmp_path / "out_a")
    result_b = evaluate_baseline(tmp_path / "out_b")

    assert result_a.report.node_metrics == result_b.report.node_metrics
    assert result_a.report.edge_metrics == result_b.report.edge_metrics
    assert result_a.report.grounding == result_b.report.grounding


def test_baseline_matches_committed_reference_metrics(tmp_path):
    result = evaluate_baseline(tmp_path / "baseline_out")
    committed = _load_committed_baseline()

    assert result.report.node_metrics.precision == committed["nodes"]["precision"]
    assert result.report.node_metrics.recall == committed["nodes"]["recall"]
    assert result.report.node_metrics.f1 == committed["nodes"]["f1"]
    assert result.report.edge_metrics.precision == committed["edges"]["precision"]
    assert result.report.edge_metrics.recall == committed["edges"]["recall"]
    assert result.report.edge_metrics.f1 == committed["edges"]["f1"]
    assert result.report.grounding == committed["grounding"]


def test_baseline_does_not_regress_below_committed_reference(tmp_path):
    """Guard against future extraction/pipeline regressions."""
    result = evaluate_baseline(tmp_path / "baseline_out")
    committed = _load_committed_baseline()

    assert result.report.node_metrics.f1 >= committed["nodes"]["f1"]
    assert result.report.edge_metrics.f1 >= committed["edges"]["f1"]
    assert result.report.grounding >= committed["grounding"]
