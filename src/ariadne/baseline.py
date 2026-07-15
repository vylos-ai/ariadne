"""Phase 1 baseline: extract -> validate -> eval, wired together, offline.

Ties the whole Phase 1 loop together end-to-end using the Phase 0 gold
standard fixtures (``tests/fixtures/returned_order``): run the extraction
pipeline over each of the three source documents, merge the resulting
evidence-grounded graphs, validate provenance, and eval against the
hand-authored gold graph.

The provider used here is deliberately *recorded*, not the generic
``FakeExtractionProvider`` default: each source document's payload is
derived directly from ``gold_graph.json`` by filtering to the nodes/edges
whose ``evidence_ids`` reference that document's Evidence node. This keeps
the run fully offline and deterministic (no network, no live LLM calls)
while still producing a meaningful score against the gold standard, rather
than an arbitrary canned payload unrelated to the fixtures.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ariadne.eval import EvalReport, evaluate
from ariadne.extraction import FakeExtractionProvider
from ariadne.graph_store import InMemoryGraphStore
from ariadne.pipeline import run_extraction_pipeline
from ariadne.schema import EdgeType, NodeType
from ariadne.validation import Violation, validate

FIXTURES_DIR = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "returned_order"
)
GOLD_GRAPH_PATH = FIXTURES_DIR / "gold_graph.json"

# Maps each Phase 0 source document to the id of its Evidence node in the
# hand-authored gold graph.
_GOLD_EVIDENCE_ID_BY_SOURCE = {
    "email_customer_complaint.txt": "evidence-email-customer-complaint",
    "email_warehouse_escalation.txt": "evidence-email-warehouse-escalation",
    "interview_ops_lead.txt": "evidence-interview-ops-lead",
}

SOURCE_DOCS = tuple(_GOLD_EVIDENCE_ID_BY_SOURCE)


def _load_gold_dict() -> dict:
    return json.loads(GOLD_GRAPH_PATH.read_text())


def load_gold_store() -> InMemoryGraphStore:
    store = InMemoryGraphStore()
    store.load(GOLD_GRAPH_PATH)
    return store


def recorded_payload_for_source(gold: dict, source_doc: str) -> dict:
    """Recorded extraction payload for one source doc, derived from gold.

    Filters the gold graph down to the nodes/edges evidenced by
    ``source_doc``'s Evidence node -- a deterministic, offline stand-in for
    "what a good extractor would find in this document" that is grounded in
    the hand-authored Phase 0 reference rather than invented ad hoc. Also
    pulls in any node referenced as an edge endpoint even if that node
    itself isn't independently evidenced by this source (an edge can only
    be added to a graph store once both its endpoint nodes exist).
    """
    evidence_id = _GOLD_EVIDENCE_ID_BY_SOURCE[source_doc]
    edges = [e for e in gold["edges"] if evidence_id in e.get("evidence_ids", [])]
    endpoint_ids = {e["source"] for e in edges} | {e["target"] for e in edges}

    nodes = [
        n
        for n in gold["nodes"]
        if n["id"] == evidence_id
        or evidence_id in n.get("evidence_ids", [])
        or n["id"] in endpoint_ids
    ]
    return {"nodes": nodes, "edges": edges}


def _merge_into(merged: InMemoryGraphStore, store: InMemoryGraphStore) -> None:
    for node_type in NodeType:
        for node in store.by_type(node_type):
            merged.add_node(node)
    for edge_type in EdgeType:
        for edge in store.by_type(edge_type):
            merged.add_edge(edge)


def run_baseline(output_dir: str | Path) -> InMemoryGraphStore:
    """Run the offline recorded-payload pipeline over every Phase 0 source.

    Each source document is run through ``run_extraction_pipeline`` (its own
    subdirectory under ``output_dir``, since the pipeline writes one
    graph/vault per call) with a recorded, gold-derived provider, then the
    resulting per-source graphs are merged into a single combined store.
    """
    gold = _load_gold_dict()
    output_dir = Path(output_dir)
    merged = InMemoryGraphStore()

    for source_doc in SOURCE_DOCS:
        payload = recorded_payload_for_source(gold, source_doc)
        provider = FakeExtractionProvider(payload)
        source_path = FIXTURES_DIR / source_doc
        source_store = run_extraction_pipeline(
            source_path, output_dir / source_path.stem, provider
        )
        _merge_into(merged, source_store)

    return merged


@dataclass
class BaselineResult:
    graph: InMemoryGraphStore
    violations: list[Violation]
    report: EvalReport


def evaluate_baseline(output_dir: str | Path) -> BaselineResult:
    """Run the baseline pipeline, validate provenance, and eval vs gold."""
    graph = run_baseline(output_dir)
    violations = validate(graph)
    report = evaluate(graph, load_gold_store())
    return BaselineResult(graph=graph, violations=violations, report=report)
