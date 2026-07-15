"""Phase 0 gold standard: the hand-authored reference graph for the
"how do we handle a returned order" process.

These tests don't test extraction (there isn't any yet) -- they assert
that the human-authored gold graph fixture is well-formed: it loads
cleanly, every edge carries provenance back to a source document, and it
renders to the committed reference vault.
"""

from pathlib import Path

from ariadne.graph_store import InMemoryGraphStore
from ariadne.schema import EdgeType, NodeType
from ariadne.vault import render_node, render_vault

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "returned_order"
GOLD_GRAPH_PATH = FIXTURE_DIR / "gold_graph.json"
VAULT_DIR = FIXTURE_DIR / "vault"


def _load_gold_store() -> InMemoryGraphStore:
    store = InMemoryGraphStore()
    store.load(GOLD_GRAPH_PATH)
    return store


def test_source_documents_exist():
    docs = [p for p in FIXTURE_DIR.iterdir() if p.is_file() and p.suffix != ".json"]
    assert 2 <= len(docs) <= 3


def test_gold_graph_loads_without_errors():
    store = _load_gold_store()
    assert store.by_type(NodeType.PROCESS_STEP)


def test_gold_graph_exercises_expected_node_types():
    store = _load_gold_store()
    used_types = {
        node.type for node_type in NodeType for node in store.by_type(node_type)
    }
    # Must exercise the majority of the schema's node types on a process
    # this small -- proves the schema is fit for purpose, not just the
    # trivially-easy ones.
    assert {
        NodeType.PROCESS_STEP,
        NodeType.DECISION,
        NodeType.ROLE,
        NodeType.SYSTEM,
        NodeType.DATA_OBJECT,
        NodeType.EXCEPTION,
        NodeType.POLICY,
        NodeType.EVIDENCE,
    }.issubset(used_types)


def test_every_edge_has_evidence():
    store = _load_gold_store()
    all_edges = [e for edge_type in EdgeType for e in store.by_type(edge_type)]
    assert all_edges
    for edge in all_edges:
        assert edge.evidence_ids, f"edge {edge.type} {edge.source}->{edge.target}"


def test_evidence_nodes_reference_source_documents():
    store = _load_gold_store()
    evidence_nodes = store.by_type(NodeType.EVIDENCE)
    assert evidence_nodes
    source_files = {
        p.name for p in FIXTURE_DIR.iterdir() if p.is_file() and p.suffix != ".json"
    }
    for evidence in evidence_nodes:
        source = evidence.properties.get("source")
        assert source in source_files, f"evidence {evidence.id} has no valid source"


def test_gold_graph_renders_one_vault_file_per_node(tmp_path):
    store = _load_gold_store()
    out_dir = tmp_path / "vault"
    render_vault(store, out_dir)

    all_node_ids = {
        node.id for node_type in NodeType for node in store.by_type(node_type)
    }
    written = {f.stem for f in out_dir.glob("*.md")}
    assert written == all_node_ids


def test_committed_reference_vault_matches_current_render(tmp_path):
    store = _load_gold_store()
    out_dir = tmp_path / "vault"
    render_vault(store, out_dir)

    committed_files = sorted(VAULT_DIR.glob("*.md"))
    assert committed_files, "reference vault must be committed"
    rendered_files = sorted(out_dir.glob("*.md"))
    assert [f.name for f in committed_files] == [f.name for f in rendered_files]
    for committed, rendered in zip(committed_files, rendered_files, strict=True):
        assert committed.read_bytes() == rendered.read_bytes()


def test_render_node_produces_nonempty_markdown_for_every_node():
    store = _load_gold_store()
    for node_type in NodeType:
        for node in store.by_type(node_type):
            text = render_node(node, store)
            assert text.startswith("---\n")
