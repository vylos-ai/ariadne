"""Tests for the read-only web API (task 0025).

Backend-neutrality is asserted by parametrizing over an ``InMemoryGraphStore``
loaded from the gold fixture ``.json`` and a ``SqliteGraphStore`` populated
from the same fixture -- mirroring the parametrized fixture in
``test_graph_store.py``. The app must behave identically regardless of which
``GraphStore`` implementation it was built with.
"""

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from ariadne.graph_store import InMemoryGraphStore
from ariadne.sqlite_store import SqliteGraphStore
from ariadne.web import build_app

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "returned_order"
GOLD_GRAPH_PATH = FIXTURE_DIR / "gold_graph.json"


def _gold_memory_store() -> InMemoryGraphStore:
    store = InMemoryGraphStore()
    store.load(GOLD_GRAPH_PATH)
    return store


def _gold_sqlite_store(tmp_path) -> SqliteGraphStore:
    memory = _gold_memory_store()
    sqlite_store = SqliteGraphStore(tmp_path / "graph.db")
    for node in memory._nodes.values():
        sqlite_store.add_node(node)
    for edge in memory._edges:
        sqlite_store.add_edge(edge)
    return sqlite_store


@pytest.fixture(params=["memory", "sqlite"])
def client(request, tmp_path):
    if request.param == "memory":
        store = _gold_memory_store()
    else:
        store = _gold_sqlite_store(tmp_path)
    app = build_app(store)
    return TestClient(app)


def test_get_graph_returns_nodes_edges_and_counts(client):
    response = client.get("/api/graph")

    assert response.status_code == 200
    body = response.json()
    assert body["nodes"]
    assert body["edges"]
    assert "counts" in body
    assert sum(body["counts"].values()) == len(body["nodes"])

    evidence_nodes = [n for n in body["nodes"] if n["is_evidence"]]
    process_nodes = [n for n in body["nodes"] if not n["is_evidence"]]
    assert evidence_nodes
    assert process_nodes
    assert all(n["type"] == "Evidence" for n in evidence_nodes)


def test_get_node_returns_node_with_facts(client):
    response = client.get("/api/nodes/step-inspect-item")

    assert response.status_code == 200
    body = response.json()
    assert body["node"]["id"] == "step-inspect-item"
    assert body["facts"]
    for fact in body["facts"]:
        assert "edge_type" in fact
        assert "direction" in fact
        assert "neighbor_id" in fact
        assert "neighbor_label" in fact
        assert "evidence_ids" in fact


def test_get_node_unknown_id_returns_json_404(client):
    response = client.get("/api/nodes/node-does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]


def test_get_evidence_returns_text_and_source(client):
    response = client.get("/api/evidence/evidence-interview-ops-lead")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "evidence-interview-ops-lead"
    assert "text" in body
    assert "source" in body
    assert body["source"] == "interview_ops_lead.txt"


def test_get_evidence_unknown_id_returns_json_404(client):
    response = client.get("/api/evidence/node-does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]


def test_get_mermaid_returns_export_source(client):
    response = client.get("/api/mermaid")

    assert response.status_code == 200
    body = response.json()
    assert "flowchart TD" in body["mermaid"]
