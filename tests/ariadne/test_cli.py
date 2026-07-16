"""Tests for the ariadne CLI's ``extract`` subcommand.

These tests must never touch the network: the live Anthropic provider
factory is monkeypatched out and replaced with the offline
``FakeExtractionProvider``.
"""

import json
from pathlib import Path

import ariadne.cli as cli
from ariadne.extraction import FakeExtractionProvider

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "returned_order"
GOLD_GRAPH_PATH = FIXTURE_DIR / "gold_graph.json"


def test_extract_subcommand_writes_graph_and_vault(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "_default_provider", lambda: FakeExtractionProvider())

    source = tmp_path / "transcript.txt"
    source.write_text("We receive the returned order and log it.")
    output_dir = tmp_path / "out"

    exit_code = cli.main(["extract", str(source), "--output-dir", str(output_dir)])

    assert exit_code == 0
    assert (output_dir / "graph.json").exists()
    assert (output_dir / "vault").is_dir()
    assert list((output_dir / "vault").glob("*.md"))


def test_extract_subcommand_accepts_multiple_sources_and_merges_graph(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(cli, "_default_provider", lambda: FakeExtractionProvider())

    source_a = tmp_path / "a.txt"
    source_a.write_text("We receive the returned order and log it.")
    source_b = tmp_path / "b.txt"
    source_b.write_text("We inspect the returned item for damage.")
    output_dir = tmp_path / "out"

    exit_code = cli.main(
        [
            "extract",
            str(source_a),
            str(source_b),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    graph = json.loads((output_dir / "graph.json").read_text())
    evidence_sources = {
        n["properties"]["source"]
        for n in graph["nodes"]
        if n["type"] == "Evidence" and "source" in n["properties"]
    }
    assert evidence_sources == {str(source_a), str(source_b)}


def test_extract_subcommand_default_output_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "_default_provider", lambda: FakeExtractionProvider())
    monkeypatch.chdir(tmp_path)

    source = tmp_path / "transcript.txt"
    source.write_text("We receive the returned order and log it.")

    exit_code = cli.main(["extract", str(source)])

    assert exit_code == 0
    assert Path("output/graph.json").exists()


def test_validate_subcommand_exits_zero_for_clean_graph(capsys):
    exit_code = cli.main(["validate", str(GOLD_GRAPH_PATH)])

    assert exit_code == 0
    assert "no provenance violations" in capsys.readouterr().out


def test_validate_subcommand_exits_nonzero_and_prints_violations(tmp_path, capsys):
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": "step-a",
                        "type": "ProcessStep",
                        "properties": {},
                        "evidence_ids": ["evidence-does-not-exist"],
                    }
                ],
                "edges": [],
            }
        )
    )

    exit_code = cli.main(["validate", str(graph_path)])

    captured = capsys.readouterr().out
    assert exit_code != 0
    assert "evidence-does-not-exist" in captured


def test_eval_subcommand_prints_metrics(capsys):
    exit_code = cli.main(["eval", str(GOLD_GRAPH_PATH), str(GOLD_GRAPH_PATH)])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Nodes" in output
    assert "Edges" in output
    assert "Grounding" in output
    assert "100.0%" in output


def test_resolve_subcommand_writes_resolved_graph_and_vault(tmp_path):
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": "ev-1",
                        "type": "Evidence",
                        "properties": {"text": "some source text"},
                        "evidence_ids": [],
                    },
                    {
                        "id": "role-support-a",
                        "type": "Role",
                        "properties": {"name": "Support"},
                        "evidence_ids": ["ev-1"],
                    },
                    {
                        "id": "role-support-b",
                        "type": "Role",
                        "properties": {"name": "Support"},
                        "evidence_ids": ["ev-1"],
                    },
                ],
                "edges": [],
            }
        )
    )
    output_dir = tmp_path / "out"

    exit_code = cli.main(["resolve", str(graph_path), "--output-dir", str(output_dir)])

    assert exit_code == 0
    resolved = json.loads((output_dir / "graph.json").read_text())
    role_nodes = [n for n in resolved["nodes"] if n["type"] == "Role"]
    assert len(role_nodes) == 1
    assert (output_dir / "vault").is_dir()
    assert list((output_dir / "vault").glob("*.md"))


def test_resolve_subcommand_output_passes_validation(tmp_path, capsys):
    output_dir = tmp_path / "out"
    cli.main(["resolve", str(GOLD_GRAPH_PATH), "--output-dir", str(output_dir)])

    exit_code = cli.main(["validate", str(output_dir / "graph.json")])

    assert exit_code == 0
    assert "no provenance violations" in capsys.readouterr().out


def test_query_find_prints_ranked_matches(capsys):
    exit_code = cli.main(["query", str(GOLD_GRAPH_PATH), "find", "warehouse"])

    assert exit_code == 0
    assert "role-warehouse" in capsys.readouterr().out


def test_query_describe_prints_node_and_evidence(capsys):
    exit_code = cli.main(
        ["query", str(GOLD_GRAPH_PATH), "describe", "step-inspect-item"]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "step-inspect-item" in output
    assert "evidence" in output


def test_query_describe_unknown_node_exits_nonzero(capsys):
    exit_code = cli.main(
        ["query", str(GOLD_GRAPH_PATH), "describe", "node-does-not-exist"]
    )

    assert exit_code != 0
    assert "no such node" in capsys.readouterr().out


def test_query_walk_prints_neighbors(capsys):
    exit_code = cli.main(["query", str(GOLD_GRAPH_PATH), "walk", "step-open-rma"])

    assert exit_code == 0
    assert "step-send-label" in capsys.readouterr().out


def test_query_path_prints_node_chain(capsys):
    exit_code = cli.main(
        ["query", str(GOLD_GRAPH_PATH), "path", "step-open-rma", "step-process-refund"]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "step-open-rma" in output
    assert "step-process-refund" in output


def test_query_what_happens_prints_downstream_nodes(capsys):
    exit_code = cli.main(
        ["query", str(GOLD_GRAPH_PATH), "what-happens", "step-open-rma"]
    )

    assert exit_code == 0
    assert "step-send-label" in capsys.readouterr().out
