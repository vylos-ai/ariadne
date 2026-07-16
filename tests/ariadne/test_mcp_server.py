"""Tests for the MCP server (Phase 3): tools mapping 1:1 onto the query layer.

In-process only -- no subprocess/stdio integration. Tools are registered via
FastMCP; we reach into the tool manager to call the underlying handler
functions directly and assert on the JSON-serializable dict results,
including the grounding ``evidence_ids`` (see CLAUDE.md's trust boundary).
"""

from pathlib import Path

import pytest

from ariadne.graph_store import InMemoryGraphStore
from ariadne.mcp_server import build_server

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "returned_order"
GOLD_GRAPH_PATH = FIXTURE_DIR / "gold_graph.json"

EXPECTED_TOOL_NAMES = {"find_nodes", "describe", "walk", "path", "what_happens"}


def _gold_store() -> InMemoryGraphStore:
    store = InMemoryGraphStore()
    store.load(GOLD_GRAPH_PATH)
    return store


def _tools_by_name(server):
    return {tool.name: tool for tool in server._tool_manager.list_tools()}


def test_all_five_tools_registered_with_descriptions():
    server = build_server(_gold_store())

    tools = _tools_by_name(server)

    assert set(tools) == EXPECTED_TOOL_NAMES
    for tool in tools.values():
        assert tool.description


def test_find_nodes_tool_returns_scored_matches():
    server = build_server(_gold_store())

    result = _tools_by_name(server)["find_nodes"].fn(text="warehouse")

    assert result["results"]
    assert result["results"][0]["node"]["id"] == "role-warehouse"
    assert result["results"][0]["score"] > 0.5


def test_describe_tool_includes_facts_with_evidence():
    server = build_server(_gold_store())

    result = _tools_by_name(server)["describe"].fn(node_id="step-inspect-item")

    assert result["node"]["id"] == "step-inspect-item"
    assert result["facts"]
    for fact in result["facts"]:
        assert fact["evidence_ids"]

    owner_facts = [f for f in result["facts"] if f["edge_type"] == "owned_by"]
    assert len(owner_facts) == 1
    assert owner_facts[0]["neighbor"]["id"] == "role-warehouse"

    trigger_facts = [f for f in result["facts"] if f["edge_type"] == "triggers"]
    assert trigger_facts
    assert all(f["evidence_ids"] for f in trigger_facts)


def test_describe_tool_unknown_id_returns_empty_result():
    server = build_server(_gold_store())

    result = _tools_by_name(server)["describe"].fn(node_id="node-does-not-exist")

    assert result["node"] is None
    assert result["facts"] == []


def test_walk_tool_filters_by_direction():
    server = build_server(_gold_store())

    result = _tools_by_name(server)["walk"].fn(
        node_id="step-send-label", direction="in"
    )

    assert len(result["facts"]) == 1
    assert result["facts"][0]["neighbor"]["id"] == "step-open-rma"
    assert result["facts"][0]["evidence_ids"]


def test_walk_tool_filters_by_edge_type():
    server = build_server(_gold_store())

    result = _tools_by_name(server)["walk"].fn(
        node_id="step-open-rma", edge_type="produces", direction="out"
    )

    assert len(result["facts"]) == 1
    assert result["facts"][0]["neighbor"]["id"] == "data-return-request"


def test_walk_tool_unknown_id_returns_empty():
    server = build_server(_gold_store())

    result = _tools_by_name(server)["walk"].fn(node_id="node-does-not-exist")

    assert result["facts"] == []


def test_path_tool_returns_nodes_and_evidenced_edges():
    server = build_server(_gold_store())

    result = _tools_by_name(server)["path"].fn(
        from_id="step-open-rma", to_id="step-process-refund"
    )

    node_ids = [node["id"] for node in result["nodes"]]
    assert node_ids[0] == "step-open-rma"
    assert node_ids[-1] == "step-process-refund"
    assert len(result["edges"]) == len(result["nodes"]) - 1
    assert all(edge["evidence_ids"] for edge in result["edges"])


def test_path_tool_no_path_returns_empty():
    server = build_server(_gold_store())

    result = _tools_by_name(server)["path"].fn(
        from_id="step-open-rma", to_id="node-does-not-exist"
    )

    assert result["nodes"] == []
    assert result["edges"] == []


def test_what_happens_tool_follows_downstream_closure():
    server = build_server(_gold_store())

    result = _tools_by_name(server)["what_happens"].fn(node_id="step-open-rma")

    reached_ids = {f["neighbor"]["id"] for f in result["facts"]}
    assert "step-inspect-item" in reached_ids
    assert all(f["evidence_ids"] for f in result["facts"])


def test_what_happens_tool_unknown_id_returns_empty():
    server = build_server(_gold_store())

    result = _tools_by_name(server)["what_happens"].fn(node_id="node-does-not-exist")

    assert result["facts"] == []


def test_cli_mcp_subcommand_builds_and_runs_server(monkeypatch):
    from ariadne import cli

    ran = {}

    def fake_run(self, *args, **kwargs):
        ran["called"] = True

    monkeypatch.setattr("mcp.server.fastmcp.FastMCP.run", fake_run)

    exit_code = cli.main(["mcp", str(GOLD_GRAPH_PATH)])

    assert exit_code == 0
    assert ran.get("called") is True


def test_cli_mcp_subcommand_errors_on_missing_graph():
    from ariadne import cli

    with pytest.raises(FileNotFoundError):
        cli.main(["mcp", "/no/such/graph.json"])
