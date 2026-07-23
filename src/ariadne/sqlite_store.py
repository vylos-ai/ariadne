"""SQLite-backed ``GraphStore`` implementation.

The ``GraphStore`` protocol (see ``graph_store.py``) was written with a
future Kùzu backend in mind, but Kùzu was archived by its vendor in October
2025. Ariadne needs durable, indexed storage rather than a query engine --
all multi-hop traversal already lives in Python in ``query.py`` -- so the
backend is stdlib ``sqlite3``: one file, zero new dependencies.

``properties`` and ``evidence_ids`` are stored as JSON text columns and
round-tripped through the same ``node_to_dict`` / ``node_from_dict`` /
``edge_to_dict`` / ``edge_from_dict`` helpers used by ``InMemoryGraphStore``,
so there is exactly one serialization path for the domain model regardless
of backend. ``save()`` / ``load()`` remain JSON export/import, matching
``InMemoryGraphStore``, so existing fixtures and the eval harness are
backend-agnostic.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ariadne.schema import (
    Edge,
    EdgeType,
    Node,
    NodeType,
    edge_from_dict,
    edge_to_dict,
    node_from_dict,
    node_to_dict,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes(
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    properties TEXT NOT NULL,
    evidence_ids TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS edges(
    type TEXT NOT NULL,
    source TEXT NOT NULL REFERENCES nodes(id),
    target TEXT NOT NULL REFERENCES nodes(id),
    evidence_ids TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS edges_source ON edges(source);
CREATE INDEX IF NOT EXISTS edges_target ON edges(target);
CREATE INDEX IF NOT EXISTS nodes_type ON nodes(type);
"""


class SqliteGraphStore:
    """SQLite-backed reference implementation of ``GraphStore``.

    SQLite foreign keys are off by default, so the ``REFERENCES`` clause in
    the schema is documentation, not enforcement -- the dangling-endpoint
    guard in ``add_edge`` is implemented in Python to match
    ``InMemoryGraphStore``'s behaviour exactly (same error messages).
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._conn = sqlite3.connect(self._path)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def add_node(self, node: Node) -> None:
        data = node_to_dict(node)
        self._conn.execute(
            """
            INSERT INTO nodes(id, type, properties, evidence_ids)
            VALUES (:id, :type, :properties, :evidence_ids)
            ON CONFLICT(id) DO UPDATE SET
                type = excluded.type,
                properties = excluded.properties,
                evidence_ids = excluded.evidence_ids
            """,
            {
                "id": data["id"],
                "type": data["type"],
                "properties": json.dumps(data["properties"]),
                "evidence_ids": json.dumps(data["evidence_ids"]),
            },
        )
        self._conn.commit()

    def add_edge(self, edge: Edge) -> None:
        if self.get_node(edge.source) is None:
            raise ValueError(
                f"cannot add edge: source node {edge.source!r} does not exist"
            )
        if self.get_node(edge.target) is None:
            raise ValueError(
                f"cannot add edge: target node {edge.target!r} does not exist"
            )
        data = edge_to_dict(edge)
        self._conn.execute(
            """
            INSERT INTO edges(type, source, target, evidence_ids)
            VALUES (:type, :source, :target, :evidence_ids)
            """,
            {
                "type": data["type"],
                "source": data["source"],
                "target": data["target"],
                "evidence_ids": json.dumps(data["evidence_ids"]),
            },
        )
        self._conn.commit()

    def get_node(self, node_id: str) -> Node | None:
        row = self._conn.execute(
            "SELECT id, type, properties, evidence_ids FROM nodes WHERE id = ?",
            (node_id,),
        ).fetchone()
        if row is None:
            return None
        return self._node_from_row(row)

    def neighbors(self, node_id: str, edge_type: EdgeType | None = None) -> list[Edge]:
        query = (
            "SELECT type, source, target, evidence_ids FROM edges "
            "WHERE (source = :node_id OR target = :node_id)"
        )
        params: dict[str, str] = {"node_id": node_id}
        if edge_type is not None:
            query += " AND type = :edge_type"
            params["edge_type"] = edge_type.value
        rows = self._conn.execute(query, params).fetchall()
        return [self._edge_from_row(row) for row in rows]

    def by_type(self, type_: NodeType | EdgeType) -> list[Node] | list[Edge]:
        if isinstance(type_, NodeType):
            rows = self._conn.execute(
                "SELECT id, type, properties, evidence_ids FROM nodes WHERE type = ?",
                (type_.value,),
            ).fetchall()
            return [self._node_from_row(row) for row in rows]
        rows = self._conn.execute(
            "SELECT type, source, target, evidence_ids FROM edges WHERE type = ?",
            (type_.value,),
        ).fetchall()
        return [self._edge_from_row(row) for row in rows]

    def save(self, path: str | Path) -> None:
        nodes = self._conn.execute(
            "SELECT id, type, properties, evidence_ids FROM nodes"
        ).fetchall()
        edges = self._conn.execute(
            "SELECT type, source, target, evidence_ids FROM edges"
        ).fetchall()
        data = {
            "nodes": [node_to_dict(self._node_from_row(row)) for row in nodes],
            "edges": [edge_to_dict(self._edge_from_row(row)) for row in edges],
        }
        Path(path).write_text(json.dumps(data, indent=2))

    def load(self, path: str | Path) -> None:
        data = json.loads(Path(path).read_text())
        self._conn.execute("DELETE FROM edges")
        self._conn.execute("DELETE FROM nodes")
        for node_data in data.get("nodes", []):
            self.add_node(node_from_dict(node_data))
        for edge_data in data.get("edges", []):
            self.add_edge(edge_from_dict(edge_data))
        self._conn.commit()

    @staticmethod
    def _node_from_row(row: tuple) -> Node:
        node_id, type_, properties, evidence_ids = row
        return node_from_dict(
            {
                "id": node_id,
                "type": type_,
                "properties": json.loads(properties),
                "evidence_ids": json.loads(evidence_ids),
            }
        )

    @staticmethod
    def _edge_from_row(row: tuple) -> Edge:
        type_, source, target, evidence_ids = row
        return edge_from_dict(
            {
                "type": type_,
                "source": source,
                "target": target,
                "evidence_ids": json.loads(evidence_ids),
            }
        )
