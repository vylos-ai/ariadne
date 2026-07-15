"""Provenance validator: the trust-boundary gate described in CLAUDE.md.

``Edge.__post_init__`` already refuses to construct a non-exempt edge with
no evidence at all, so this module focuses on what construction can't catch
once nodes/edges exist together in a graph: evidence references that don't
resolve to any node, and evidence references that resolve to a node that
isn't an ``Evidence`` node.
"""

from __future__ import annotations

from dataclasses import dataclass

from ariadne.graph_store import GraphStore
from ariadne.schema import EdgeType, NodeType

_EVIDENCE_EXEMPT_EDGE_TYPES = {EdgeType.EVIDENCED_BY}


@dataclass
class Violation:
    """A single provenance rule violation, ready to be printed."""

    kind: str
    subject: str
    message: str

    def __str__(self) -> str:
        return f"[{self.kind}] {self.subject}: {self.message}"


def _all_nodes(graph: GraphStore) -> list:
    nodes = []
    for node_type in NodeType:
        nodes.extend(graph.by_type(node_type))
    return nodes


def _all_edges(graph: GraphStore) -> list:
    edges = []
    for edge_type in EdgeType:
        edges.extend(graph.by_type(edge_type))
    return edges


def _check_evidence_ids(
    graph: GraphStore, evidence_ids: list[str], subject: str
) -> list[Violation]:
    violations = []
    for evidence_id in evidence_ids:
        evidence_node = graph.get_node(evidence_id)
        if evidence_node is None:
            violations.append(
                Violation(
                    kind="dangling_evidence",
                    subject=subject,
                    message=(
                        f"evidence id {evidence_id!r} does not resolve to any "
                        "node in the graph"
                    ),
                )
            )
        elif evidence_node.type != NodeType.EVIDENCE:
            violations.append(
                Violation(
                    kind="evidence_wrong_type",
                    subject=subject,
                    message=(
                        f"evidence id {evidence_id!r} resolves to a "
                        f"{evidence_node.type.value} node, not an Evidence node"
                    ),
                )
            )
    return violations


def validate(graph: GraphStore) -> list[Violation]:
    """Check every edge and every node's evidence references for provenance
    violations. Returns the full list of violations found (not just the
    first), so they can all be surfaced to a human at once.
    """
    violations: list[Violation] = []

    for node in _all_nodes(graph):
        violations.extend(_check_evidence_ids(graph, node.evidence_ids, node.id))

    for edge in _all_edges(graph):
        subject = f"{edge.type.value} edge {edge.source} -> {edge.target}"
        if edge.type not in _EVIDENCE_EXEMPT_EDGE_TYPES and not edge.evidence_ids:
            violations.append(
                Violation(
                    kind="missing_evidence",
                    subject=subject,
                    message="edge carries no evidence references",
                )
            )
        violations.extend(_check_evidence_ids(graph, edge.evidence_ids, subject))

    return violations
