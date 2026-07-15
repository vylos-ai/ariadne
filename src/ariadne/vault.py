"""Markdown vault: deterministic graph -> markdown projection.

Every node materializes as one markdown file: YAML frontmatter carries the
structured properties + evidence refs, and the body lists related nodes as
``[[node-id]]`` wiki links grouped by edge type. The vault is a *projection*
of the graph, not the source of truth (see CLAUDE.md) -- ``parse_vault_file``
exists to recover a node dict for diffing against the graph, not to support
silent write-back.

Determinism matters: identical graphs must render to byte-identical files so
vault diffs are meaningful. That means sorted frontmatter keys, sorted edge
type groups, and sorted links within each group.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from ariadne.graph_store import GraphStore
from ariadne.schema import Node

_LINK_PATTERN = re.compile(r"^-\s*\[\[(?P<target>.+)\]\]\s*$")
_HEADING_PATTERN = re.compile(r"^##\s*(?P<edge_type>.+)\s*$")


def _related_links(node: Node, store: GraphStore) -> dict[str, list[str]]:
    """Return {edge_type_value: [other_node_id, ...]}, sorted for determinism."""
    groups: dict[str, set[str]] = {}
    for edge in store.neighbors(node.id):
        other = edge.target if edge.source == node.id else edge.source
        groups.setdefault(edge.type.value, set()).add(other)
    return {edge_type: sorted(targets) for edge_type, targets in sorted(groups.items())}


def render_node(node: Node, store: GraphStore) -> str:
    """Render a single node to deterministic markdown."""
    frontmatter = {
        "id": node.id,
        "type": node.type.value,
        "properties": node.properties,
        "evidence_ids": node.evidence_ids,
    }
    frontmatter_yaml = yaml.safe_dump(
        frontmatter, sort_keys=True, default_flow_style=False
    )

    lines = [f"# {node.id}", ""]
    for edge_type, targets in _related_links(node, store).items():
        lines.append(f"## {edge_type}")
        for target in targets:
            lines.append(f"- [[{target}]]")
        lines.append("")

    body = "\n".join(lines).rstrip() + "\n"
    return f"---\n{frontmatter_yaml}---\n\n{body}"


def render_vault(store: GraphStore, vault_dir: str | Path) -> None:
    """Render every node in ``store`` to one markdown file under ``vault_dir``."""
    vault_dir = Path(vault_dir)
    vault_dir.mkdir(parents=True, exist_ok=True)
    for node in _all_nodes(store):
        text = render_node(node, store)
        (vault_dir / f"{node.id}.md").write_text(text)


def _all_nodes(store: GraphStore) -> list[Node]:
    from ariadne.schema import NodeType

    nodes: list[Node] = []
    for node_type in NodeType:
        nodes.extend(store.by_type(node_type))
    return sorted(nodes, key=lambda n: n.id)


def parse_vault_file(path: str | Path) -> dict:
    """Parse a rendered vault file back into a node dict + links, for diffing.

    This is intentionally one-directional (vault -> dict for comparison); the
    graph remains canonical and this is not used for silent write-back.
    """
    text = Path(path).read_text()
    _, frontmatter_raw, body = text.split("---\n", 2)
    frontmatter = yaml.safe_load(frontmatter_raw) or {}

    links: dict[str, list[str]] = {}
    current_edge_type: str | None = None
    for line in body.splitlines():
        heading_match = _HEADING_PATTERN.match(line)
        if heading_match:
            current_edge_type = heading_match.group("edge_type")
            links.setdefault(current_edge_type, [])
            continue
        link_match = _LINK_PATTERN.match(line)
        if link_match and current_edge_type is not None:
            links[current_edge_type].append(link_match.group("target"))

    frontmatter["links"] = links
    return frontmatter
