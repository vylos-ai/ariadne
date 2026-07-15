"""Tests for the ariadne CLI's ``extract`` subcommand.

These tests must never touch the network: the live Anthropic provider
factory is monkeypatched out and replaced with the offline
``FakeExtractionProvider``.
"""

from pathlib import Path

import ariadne.cli as cli
from ariadne.extraction import FakeExtractionProvider


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
