"""Local web API over an existing graph.

Phase "make it concrete" delivery (CLAUDE.md): the CLI's one-node-at-a-time
query loop is too abstract to build trust in the graph. This module exposes
a small, read-only JSON API so a browser UI (task 0026) can render the graph
and let a human check every fact against its evidence.

``build_app(store)`` mirrors ``mcp_server.py::build_server(store)`` -- it
takes an already-open ``GraphStore`` and never learns which backend it is.
Read-only: no mutation endpoints. Corrections-as-evidence is Phase 5 and
needs the supersede/temporal model designed first (see CLAUDE.md), so adding
writes here would bake in the wrong shape.
"""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from ariadne.eval import _all_edges, _all_nodes, _node_label
from ariadne.export import to_mermaid
from ariadne.graph_store import GraphStore
from ariadne.query import NeighborFact, describe
from ariadne.schema import Node, NodeType, edge_to_dict


def _node_to_dict(node: Node) -> dict:
    return {
        "id": node.id,
        "type": node.type.value,
        "label": _node_label(node),
        "properties": node.properties,
        "evidence_ids": node.evidence_ids,
        "is_evidence": node.type == NodeType.EVIDENCE,
    }


def _fact_to_dict(fact: NeighborFact) -> dict:
    return {
        "edge_type": fact.edge.type.value,
        "direction": fact.direction,
        "neighbor_id": fact.neighbor.id,
        "neighbor_label": fact.neighbor_label,
        "evidence_ids": fact.evidence_ids,
    }


def _not_found(node_id: str) -> JSONResponse:
    return JSONResponse({"error": f"no such node: {node_id!r}"}, status_code=404)


def build_app(store: GraphStore) -> Starlette:
    """Build a read-only Starlette app exposing ``store`` as a JSON API."""

    async def get_graph(request: Request) -> JSONResponse:
        nodes = _all_nodes(store)
        edges = _all_edges(store)
        counts: dict[str, int] = {}
        for node in nodes:
            counts[node.type.value] = counts.get(node.type.value, 0) + 1
        return JSONResponse(
            {
                "nodes": [_node_to_dict(node) for node in nodes],
                "edges": [edge_to_dict(edge) for edge in edges],
                "counts": counts,
            }
        )

    async def get_node(request: Request) -> JSONResponse:
        node_id = request.path_params["node_id"]
        node, facts = describe(store, node_id)
        if node is None:
            return _not_found(node_id)
        return JSONResponse(
            {
                "node": _node_to_dict(node),
                "facts": [_fact_to_dict(fact) for fact in facts],
            }
        )

    async def get_evidence(request: Request) -> JSONResponse:
        node_id = request.path_params["node_id"]
        node = store.get_node(node_id)
        if node is None:
            return _not_found(node_id)
        return JSONResponse(
            {
                "id": node.id,
                "text": node.properties.get("text"),
                "source": node.properties.get("source"),
            }
        )

    async def get_mermaid(request: Request) -> JSONResponse:
        return JSONResponse({"mermaid": to_mermaid(store)})

    return Starlette(
        routes=[
            Route("/api/graph", get_graph),
            Route("/api/nodes/{node_id}", get_node),
            Route("/api/evidence/{node_id}", get_evidence),
            Route("/api/mermaid", get_mermaid),
        ]
    )
