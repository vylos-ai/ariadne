"""Tests for the extraction pipeline: source doc -> evidence-grounded graph."""

from pathlib import Path

from ariadne.extraction import FakeExtractionProvider
from ariadne.graph_store import InMemoryGraphStore
from ariadne.pipeline import run_extraction_pipeline
from ariadne.schema import EdgeType, NodeType

SOURCE_TEXT = "We receive the returned order and log it in the system."


def _write_source(tmp_path: Path, text: str = SOURCE_TEXT) -> Path:
    source = tmp_path / "transcript.txt"
    source.write_text(text)
    return source


def test_source_document_becomes_evidence_node(tmp_path):
    source = _write_source(tmp_path)
    output_dir = tmp_path / "out"

    store = run_extraction_pipeline(source, output_dir, FakeExtractionProvider())

    evidence_nodes = store.by_type(NodeType.EVIDENCE)
    source_evidence = [
        n for n in evidence_nodes if n.properties.get("source") == str(source)
    ]
    assert len(source_evidence) == 1
    assert source_evidence[0].properties["text"] == SOURCE_TEXT


def test_every_extracted_edge_references_source_evidence(tmp_path):
    source = _write_source(tmp_path)
    output_dir = tmp_path / "out"

    store = run_extraction_pipeline(source, output_dir, FakeExtractionProvider())

    evidence_id = [
        n.id
        for n in store.by_type(NodeType.EVIDENCE)
        if n.properties.get("source") == str(source)
    ][0]

    all_edges = []
    for node_type in NodeType:
        for node in store.by_type(node_type):
            all_edges.extend(store.neighbors(node.id))
    # dedup by identity via source/target/type since neighbors returns dupes across both endpoints
    seen = set()
    unique_edges = []
    for edge in all_edges:
        key = (edge.type, edge.source, edge.target)
        if key not in seen:
            seen.add(key)
            unique_edges.append(edge)

    assert unique_edges  # sanity: the fake provider's canned payload has edges
    for edge in unique_edges:
        assert evidence_id in edge.evidence_ids


def test_writes_graph_json_and_vault_directory(tmp_path):
    source = _write_source(tmp_path)
    output_dir = tmp_path / "out"

    run_extraction_pipeline(source, output_dir, FakeExtractionProvider())

    graph_path = output_dir / "graph.json"
    vault_dir = output_dir / "vault"
    assert graph_path.exists()
    assert vault_dir.is_dir()
    assert list(vault_dir.glob("*.md"))


def test_output_graph_loads_and_passes_provenance_checks(tmp_path):
    source = _write_source(tmp_path)
    output_dir = tmp_path / "out"

    run_extraction_pipeline(source, output_dir, FakeExtractionProvider())

    loaded = InMemoryGraphStore()
    loaded.load(output_dir / "graph.json")

    for edge_type in EdgeType:
        for edge in loaded.by_type(edge_type):
            if edge_type != EdgeType.EVIDENCED_BY:
                assert edge.evidence_ids


def test_pipeline_is_deterministic_given_identical_provider_output(tmp_path):
    source = _write_source(tmp_path)
    out_a = tmp_path / "out_a"
    out_b = tmp_path / "out_b"

    run_extraction_pipeline(source, out_a, FakeExtractionProvider())
    run_extraction_pipeline(source, out_b, FakeExtractionProvider())

    assert (out_a / "graph.json").read_text() == (out_b / "graph.json").read_text()

    vault_a_files = sorted(p.name for p in (out_a / "vault").glob("*.md"))
    vault_b_files = sorted(p.name for p in (out_b / "vault").glob("*.md"))
    assert vault_a_files == vault_b_files
    for name in vault_a_files:
        assert (out_a / "vault" / name).read_text() == (
            out_b / "vault" / name
        ).read_text()


def test_custom_payload_is_respected(tmp_path):
    source = _write_source(tmp_path, "Custom source text about invoices.")
    output_dir = tmp_path / "out"
    payload = {
        "nodes": [
            {
                "id": "quote-1",
                "type": "Evidence",
                "properties": {"text": "AP approves the invoice"},
                "evidence_ids": [],
            },
            {
                "id": "step-invoice",
                "type": "ProcessStep",
                "properties": {"name": "Approve invoice"},
                "evidence_ids": ["quote-1"],
            },
            {
                "id": "role-ap",
                "type": "Role",
                "properties": {"name": "Accounts Payable"},
                "evidence_ids": ["quote-1"],
            },
        ],
        "edges": [
            {
                "type": "owned_by",
                "source": "step-invoice",
                "target": "role-ap",
                "evidence_ids": ["quote-1"],
            }
        ],
    }

    store = run_extraction_pipeline(source, output_dir, FakeExtractionProvider(payload))

    owned_by_edges = store.by_type(EdgeType.OWNED_BY)
    assert len(owned_by_edges) == 1
    assert "quote-1" in owned_by_edges[0].evidence_ids  # provider's own evidence kept
    assert len(owned_by_edges[0].evidence_ids) == 2  # + source evidence wired in
