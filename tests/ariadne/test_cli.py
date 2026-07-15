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
