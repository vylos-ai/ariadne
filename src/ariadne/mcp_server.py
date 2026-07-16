"""MCP server exposing the query layer as callable agent tools.

Phase 3 delivery (CLAUDE.md): "expose graph traversal + hybrid search as
callable tools (e.g. MCP server) so a general-purpose agent ... can answer
'what happens when X' questions grounded in the graph." Each tool here maps
1:1 onto a function in ``ariadne.query`` and returns a JSON-serializable
dict. Every returned fact carries its ``evidence_ids`` -- the trust boundary
from CLAUDE.md applies to tool results just as much as to the graph itself.

Unknown node ids mirror the query layer's behavior: empty results, never
exceptions.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ariadne.eval import _node_label
from ariadne.graph_store import GraphStore
from ariadne.query import describe as _describe
from ariadne.query import find_nodes as _find_nodes
from ariadne.query import path as _path
from ariadne.query import walk as _walk
from ariadne.query import what_happens as _what_happens
from ariadne.query import NeighborFact
from ariadne.schema import Edge, EdgeType, Node, edge_to_dict


def _node_to_dict(node: Node) -> dict:
    return {
        "id": node.id,
        "type": node.type.value,
        "label": _node_label(node),
        "properties": node.properties,
        "evidence_ids": node.evidence_ids,
    }


def _fact_to_dict(fact: NeighborFact) -> dict:
    return {
        "edge_type": fact.edge.type.value,
        "direction": fact.direction,
        "neighbor": _node_to_dict(fact.neighbor),
        "evidence_ids": fact.evidence_ids,
    }


def _edge_dict_list(edges: list[Edge]) -> list[dict]:
    return [edge_to_dict(edge) for edge in edges]


def build_server(store: GraphStore) -> FastMCP:
    """Build a FastMCP server with the five query tools bound to ``store``."""
    server = FastMCP("ariadne")

    @server.tool(
        description=(
            "Fuzzy-match node labels against free text and return the "
            "best-matching nodes, ranked by score."
        )
    )
    def find_nodes(text: str) -> dict:
        results = _find_nodes(store, text)
        return {
            "results": [
                {"node": _node_to_dict(r.node), "score": r.score} for r in results
            ]
        }

    @server.tool(
        description=(
            "Describe a node by id: its properties plus every incident edge "
            "(both directions), each resolved with its neighbor node and "
            "grounding evidence ids. Unknown ids return a null node and no "
            "facts."
        )
    )
    def describe(node_id: str) -> dict:
        node, facts = _describe(store, node_id)
        return {
            "node": _node_to_dict(node) if node is not None else None,
            "facts": [_fact_to_dict(fact) for fact in facts],
        }

    @server.tool(
        description=(
            "One-hop neighbors of a node, optionally filtered by edge type "
            "(e.g. 'triggers', 'owned_by') and/or direction ('out', 'in', "
            "'both', default 'both')."
        )
    )
    def walk(
        node_id: str, edge_type: str | None = None, direction: str = "both"
    ) -> dict:
        parsed_edge_type = EdgeType(edge_type) if edge_type else None
        facts = _walk(store, node_id, edge_type=parsed_edge_type, direction=direction)
        return {"facts": [_fact_to_dict(fact) for fact in facts]}

    @server.tool(
        description=(
            "Shortest path between two nodes, treating edges as traversable "
            "both ways. Returns the node chain and the evidenced edges taken; "
            "empty lists if no path exists or either id is unknown."
        )
    )
    def path(from_id: str, to_id: str) -> dict:
        result = _path(store, from_id, to_id)
        return {
            "nodes": [_node_to_dict(node) for node in result.nodes],
            "edges": _edge_dict_list(result.edges),
        }

    @server.tool(
        description=(
            "Downstream closure over 'triggers'/'produces' edges from a "
            "node -- 'what happens when X'. Each reached node comes with the "
            "edge and evidence that connects it."
        )
    )
    def what_happens(node_id: str) -> dict:
        facts = _what_happens(store, node_id)
        return {"facts": [_fact_to_dict(fact) for fact in facts]}

    return server
