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
from ariadne.extraction import ExtractionResult, FakeExtractionProvider
from ariadne.graph_store import InMemoryGraphStore
from ariadne.pipeline import run_extraction_pipeline
from ariadne.resolution import resolve
from ariadne.schema import EdgeType, NodeType
from ariadne.validation import Violation, validate
from ariadne.vault import render_vault

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


# Non-Evidence node label keys that get a slight, realistic wording tweak in
# ``interview_ops_lead.txt``'s recorded payload -- see
# ``_with_label_variation``.
_LABEL_KEYS_TO_VARY = ("name", "summary")


def _with_label_variation(payload: dict) -> dict:
    """Perturb non-Evidence node labels slightly.

    Real source documents describe the same entity with minor wording
    differences (a trailing period, a slightly different phrasing) rather
    than byte-identical text. This exercises entity resolution's *fuzzy*
    label matching (see ``ariadne.labels``) instead of only exact-duplicate
    collapsing, while staying within the fuzzy-match threshold so the
    v1 CLI's un-adjudicated ``resolve()`` still merges them.
    """
    nodes = []
    for node in payload["nodes"]:
        node = dict(node)
        if node["type"] != "Evidence":
            properties = dict(node["properties"])
            for key in _LABEL_KEYS_TO_VARY:
                if properties.get(key):
                    properties[key] = f"{properties[key]}."
            node["properties"] = properties
        nodes.append(node)
    return {"nodes": nodes, "edges": payload["edges"]}


def _scope_node_evidence_to_source(payload: dict, evidence_id: str) -> dict:
    """Restrict each non-Evidence node's evidence_ids to this source alone.

    The gold graph often lists several sources per node (an entity mentioned
    in more than one document). ``recorded_payload_for_source`` carries that
    full gold evidence list straight through -- fine for the Phase 1 baseline
    (one un-namespaced pipeline call per source, later merged), but not for a
    *single* multi-source pipeline call: ids get namespaced per source (see
    ``run_extraction_pipeline``), so a node here can't yet reference another
    source's evidence node -- that node isn't part of this source's id map --
    without the reference dangling. Scoping to this source's own evidence id
    keeps every reference resolvable within the merged graph.
    """
    nodes = []
    for node in payload["nodes"]:
        node = dict(node)
        if node["type"] != "Evidence":
            node["evidence_ids"] = [
                e for e in node.get("evidence_ids", []) if e == evidence_id
            ]
        nodes.append(node)
    return {"nodes": nodes, "edges": payload["edges"]}


def recorded_payload_for_source_phase2(gold: dict, source_doc: str) -> dict:
    """Like ``recorded_payload_for_source``, adapted for a single multi-source
    pipeline run: node evidence scoped to this source, plus a wording tweak
    for one doc.

    ``interview_ops_lead.txt`` is the end-to-end walkthrough and, per the
    gold graph, shares most of its entities with the two narrower email
    fixtures -- exactly the sort of duplicate-across-sources scenario
    resolution (0012/0013) exists to collapse. Giving its copy a slightly
    different label wording keeps the merge honest: resolution has to
    fuzzy-match, not just dedupe identical strings.
    """
    evidence_id = _GOLD_EVIDENCE_ID_BY_SOURCE[source_doc]
    payload = recorded_payload_for_source(gold, source_doc)
    payload = _scope_node_evidence_to_source(payload, evidence_id)
    if source_doc == "interview_ops_lead.txt":
        payload = _with_label_variation(payload)
    return payload


@dataclass
class _RecordedMultiSourceProvider:
    """Offline provider dispatching by source text to a per-document payload.

    Unlike the Phase 1 baseline (one provider per ``run_extraction_pipeline``
    call, one call per source), Phase 2 needs a *single* multi-source
    pipeline run -- so ids get namespaced per source and duplicate entities
    across documents survive the merge for resolution to collapse -- which
    means a single provider instance must know how to answer for each of the
    several source texts passed to ``run_extraction_pipeline``.
    """

    payload_by_text: dict[str, dict]

    def extract(self, text: str) -> ExtractionResult:
        return FakeExtractionProvider(self.payload_by_text[text]).extract(text)


def run_baseline_phase2(output_dir: str | Path) -> InMemoryGraphStore:
    """Run one multi-source pipeline call over all three Phase 0 fixtures.

    A single ``run_extraction_pipeline`` call over all three source paths
    namespaces each source's extracted node ids, so entities shared across
    documents (per the gold graph's evidence overlaps) land in the merged
    graph as distinct-but-duplicate nodes -- exactly what ``resolve()`` is
    meant to collapse.
    """
    gold = _load_gold_dict()
    source_paths = [FIXTURES_DIR / source_doc for source_doc in SOURCE_DOCS]
    payload_by_text = {
        source_path.read_text(): recorded_payload_for_source_phase2(
            gold, source_path.name
        )
        for source_path in source_paths
    }
    provider = _RecordedMultiSourceProvider(payload_by_text)
    return run_extraction_pipeline(source_paths, output_dir, provider)


@dataclass
class Phase2BaselineResult:
    unresolved_graph: InMemoryGraphStore
    resolved_graph: InMemoryGraphStore
    unresolved_violations: list[Violation]
    resolved_violations: list[Violation]
    unresolved_report: EvalReport
    resolved_report: EvalReport


def evaluate_phase2_baseline(output_dir: str | Path) -> Phase2BaselineResult:
    """Run the Phase 2 baseline: multi-source extract -> resolve -> eval.

    Evals both the unresolved (pre-resolution) and resolved graphs against
    the gold standard so resolution's effect on quality is directly
    comparable, mirroring how 0010 closed the Phase 1 loop.
    """
    output_dir = Path(output_dir)
    unresolved = run_baseline_phase2(output_dir / "unresolved")
    resolved = resolve(unresolved)

    resolved_dir = output_dir / "resolved"
    resolved_dir.mkdir(parents=True, exist_ok=True)
    resolved.save(resolved_dir / "graph.json")
    render_vault(resolved, resolved_dir / "vault")

    gold = load_gold_store()
    return Phase2BaselineResult(
        unresolved_graph=unresolved,
        resolved_graph=resolved,
        unresolved_violations=validate(unresolved),
        resolved_violations=validate(resolved),
        unresolved_report=evaluate(unresolved, gold),
        resolved_report=evaluate(resolved, gold),
    )
