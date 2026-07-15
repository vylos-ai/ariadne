"""Domain model for the process graph: nodes, edges, and provenance.

Provenance is first-class: every edge (other than an ``evidenced_by`` edge,
which *is* a provenance link) must carry at least one evidence reference.
This is the trust boundary described in CLAUDE.md -- no silent, ungrounded
facts get written into the graph.

Nodes and edges are plain dataclasses that round-trip losslessly to/from
``dict`` so they can be persisted (JSON store) and projected (markdown
vault) without a dedicated serialization layer.
"""

from dataclasses import dataclass, field
from enum import Enum


class NodeType(str, Enum):
    PROCESS_STEP = "ProcessStep"
    DECISION = "Decision"
    ROLE = "Role"
    SYSTEM = "System"
    DATA_OBJECT = "DataObject"
    EXCEPTION = "Exception"
    POLICY = "Policy"
    EVIDENCE = "Evidence"


class EdgeType(str, Enum):
    TRIGGERS = "triggers"
    REQUIRES = "requires"
    PRODUCES = "produces"
    OWNED_BY = "owned_by"
    ESCALATES_TO = "escalates_to"
    DEPENDS_ON = "depends_on"
    CONTRADICTS = "contradicts"
    SUPERSEDES = "supersedes"
    EVIDENCED_BY = "evidenced_by"


NODE_TYPES = {t.value for t in NodeType}
EDGE_TYPES = {t.value for t in EdgeType}

# Edge types that are themselves provenance links, and are therefore exempt
# from the "must carry evidence" rule.
_EVIDENCE_EXEMPT_EDGE_TYPES = {EdgeType.EVIDENCED_BY}


@dataclass
class Node:
    """A node in the process graph.

    ``properties`` holds type-specific, non-trivial data (e.g. a
    ProcessStep's name/description). ``evidence_ids`` references the
    ``Evidence`` nodes those properties were derived from.
    """

    id: str
    type: NodeType
    properties: dict = field(default_factory=dict)
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class Edge:
    """A typed, evidence-backed relationship between two nodes."""

    type: EdgeType
    source: str
    target: str
    evidence_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.type not in _EVIDENCE_EXEMPT_EDGE_TYPES and not self.evidence_ids:
            raise ValueError(
                f"edge of type {self.type!r} requires at least one evidence "
                "reference in evidence_ids (provenance is first-class)"
            )


def node_to_dict(node: Node) -> dict:
    return {
        "id": node.id,
        "type": node.type.value,
        "properties": node.properties,
        "evidence_ids": node.evidence_ids,
    }


def node_from_dict(data: dict) -> Node:
    return Node(
        id=data["id"],
        type=NodeType(data["type"]),
        properties=data.get("properties", {}),
        evidence_ids=data.get("evidence_ids", []),
    )


def edge_to_dict(edge: Edge) -> dict:
    return {
        "type": edge.type.value,
        "source": edge.source,
        "target": edge.target,
        "evidence_ids": edge.evidence_ids,
    }


def edge_from_dict(data: dict) -> Edge:
    return Edge(
        type=EdgeType(data["type"]),
        source=data["source"],
        target=data["target"],
        evidence_ids=data.get("evidence_ids", []),
    )
