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


def _namespace_id(node_id: str, digest: str) -> str:
    """Prefix an extracted node id with its source's content-hash digest.

    Two sources that each extract e.g. ``role-support`` must not collide in
    the merged graph -- entity resolution (0012), not the pipeline, decides
    whether those are "the same" role. Namespacing keeps them distinct until
    then.
    """
    return f"{digest}-{node_id}"


def _add_source_to_graph(
    source_path: str | Path,
    store: InMemoryGraphStore,
    provider: ExtractionProvider,
    namespace: bool,
) -> None:
    """Extract one source document into ``store``, namespacing its ids.

    Creates the source's ``Evidence`` node, runs ``provider`` over the text,
    then adds every extracted node/edge -- with ids namespaced to this
    source (when ``namespace`` is set, i.e. more than one source is being
    merged in this run) so they can't collide with another source's ids --
    wiring the source evidence into every extracted edge along the way.
    """
    source_path = Path(source_path)
    text = source_path.read_text()

    evidence_id = _source_evidence_id(text)
    digest = evidence_id.removeprefix("evidence-source-")
    store.add_node(
        Node(
            id=evidence_id,
            type=NodeType.EVIDENCE,
            properties={"source": str(source_path), "text": text},
        )
    )

    result = provider.extract(text)

    if namespace:
        id_map = {node.id: _namespace_id(node.id, digest) for node in result.nodes}
    else:
        id_map = {node.id: node.id for node in result.nodes}

    for node in result.nodes:
        if node.id == evidence_id:
            continue  # the source evidence node is authoritative; skip provider dupes
        node.id = id_map[node.id]
        node.evidence_ids = [id_map.get(e, e) for e in node.evidence_ids]
        store.add_node(node)

    for edge in result.edges:
        edge.source = id_map.get(edge.source, edge.source)
        edge.target = id_map.get(edge.target, edge.target)
        edge.evidence_ids = [id_map.get(e, e) for e in edge.evidence_ids]
        if evidence_id not in edge.evidence_ids:
            edge.evidence_ids = [*edge.evidence_ids, evidence_id]
        store.add_edge(edge)


def run_extraction_pipeline(
    source_paths: str | Path | list[str | Path],
    output_dir: str | Path,
    provider: ExtractionProvider,
) -> InMemoryGraphStore:
    """Run extraction over one or more source documents and persist the result.

    Each source becomes its own ``Evidence`` node, with its extracted node
    ids namespaced so identical ids from different sources don't collide --
    duplicates are left in the merged graph for entity resolution (0012) to
    collapse later. Writes ``output_dir/graph.json`` and materializes the
    vault at ``output_dir/vault``. Returns the populated store.
    """
    if isinstance(source_paths, (str, Path)):
        source_paths = [source_paths]

    store = InMemoryGraphStore()
    namespace = len(source_paths) > 1

    for source_path in source_paths:
        _add_source_to_graph(source_path, store, provider, namespace)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    store.save(output_dir / "graph.json")
    render_vault(store, output_dir / "vault")

    return store
