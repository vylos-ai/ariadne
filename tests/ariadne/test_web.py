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
    assert "source" in body
    assert body["source"] == "interview_ops_lead.txt"


def test_get_evidence_returns_full_properties_when_no_text_key(client):
    # The gold fixture's Evidence nodes store their content under "summary",
    # not "text" -- Node.properties is deliberately schema-free (CLAUDE.md),
    # so the endpoint must not hardcode/narrow to two keys and silently drop
    # everything else. The trust loop dead-ends if it does.
    response = client.get("/api/evidence/evidence-interview-ops-lead")

    assert response.status_code == 200
    body = response.json()
    assert "text" not in body or body["text"] is None
    assert "summary" in body
    assert "ops lead" in body["summary"].lower() or "marcus" in body["summary"].lower()


def test_get_evidence_unknown_id_returns_json_404(client):
    response = client.get("/api/evidence/node-does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]


def test_get_mermaid_returns_export_source(client):
    response = client.get("/api/mermaid")

    assert response.status_code == 200
    body = response.json()
    assert "flowchart TD" in body["mermaid"]


def test_root_serves_html_page(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    body = response.text
    assert "/static/app.js" in body

    # The trust loop depends on these endpoints -- assert the client-side
    # code actually references them rather than trusting it "looks right".
    app_js = client.get("/static/app.js").text
    assert "/api/graph" in app_js
    assert "/api/nodes/" in app_js
    assert "/api/evidence/" in app_js
    assert "/api/mermaid" in app_js


def test_static_assets_are_served(client):
    for path in (
        "/static/app.js",
        "/static/style.css",
        "/static/vendor/mermaid.min.js",
    ):
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.text.strip() or response.content, path


def test_mermaid_configured_without_html_labels(client):
    # Mermaid renders labels inside a foreignObject and parses them as HTML
    # by default -- downstream of any escaping, and "strict" securityLevel
    # only strips event handlers, not tags like <img>. A node name from
    # LLM-extracted content containing an <img src="..."> would make the
    # browser issue an outbound request when the diagram renders, breaking
    # the "no network calls beyond this server" constraint. htmlLabels:
    # false forces SVG <text> labels instead, closing that vector for good
    # -- assert it can't silently regress.
    app_js = client.get("/static/app.js").text
    assert "htmlLabels: false" in app_js
    assert "flowchart: { htmlLabels: false }" in app_js
