"""Extraction pipeline: source document -> evidence-grounded graph + vault.

Wires provenance in from the start (see CLAUDE.md): the source document
becomes an ``Evidence`` node, and every edge produced by the extraction
provider is guaranteed to reference it -- in addition to whatever evidence
the provider itself attached -- so nothing lands in the graph without a
pointer back to the source material.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from ariadne.extraction import ExtractionProvider
from ariadne.graph_store import InMemoryGraphStore
from ariadne.schema import Node, NodeType
from ariadne.vault import render_vault


def _source_evidence_id(text: str) -> str:
    """Deterministic id for a source document's Evidence node.

    Derived from a content hash, so identical source text always produces
    the same evidence id regardless of the file's path/name -- this is
    what makes repeated pipeline runs over the same content deterministic.
    """
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return f"evidence-source-{digest}"


def run_extraction_pipeline(
    source_path: str | Path,
    output_dir: str | Path,
    provider: ExtractionProvider,
) -> InMemoryGraphStore:
    """Run extraction over a single source document and persist the result.

    Reads ``source_path``, creates a source-level ``Evidence`` node, runs
    ``provider`` over the text, adds every extracted node/edge to a fresh
    graph store -- wiring the source evidence into every extracted edge --
    then writes ``output_dir/graph.json`` and materializes the vault at
    ``output_dir/vault``. Returns the populated store.
    """
    source_path = Path(source_path)
    text = source_path.read_text()

    store = InMemoryGraphStore()

    evidence_id = _source_evidence_id(text)
    store.add_node(
        Node(
            id=evidence_id,
            type=NodeType.EVIDENCE,
            properties={"source": str(source_path), "text": text},
        )
    )

    result = provider.extract(text)

    for node in result.nodes:
        if node.id == evidence_id:
            continue  # the source evidence node is authoritative; skip provider dupes
        store.add_node(node)

    for edge in result.edges:
        if evidence_id not in edge.evidence_ids:
            edge.evidence_ids = [*edge.evidence_ids, evidence_id]
        store.add_edge(edge)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    store.save(output_dir / "graph.json")
    render_vault(store, output_dir / "vault")

    return store
