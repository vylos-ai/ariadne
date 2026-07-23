---
status: todo
priority: high
owner:
created: 2026-07-23
updated: 2026-07-23
---

# Persistent SQLite graph store

## Description

`InMemoryGraphStore` is the only backend: every command loads a whole JSON file
into memory and writes it back, so nothing persists incrementally and
`neighbors()` is a full list scan.

The `GraphStore` protocol was written with a Kùzu backend in mind, but **Kùzu
was archived by its vendor in October 2025** (repo read-only, `kuzudb.com` no
longer resolves). Ariadne needs durable storage, not a query engine — multi-hop
traversal already lives in Python in `query.py` — so the backend is stdlib
`sqlite3`: one file, zero new dependencies, indexed edge lookups, nothing left
to be abandoned.

## Acceptance Criteria

- [ ] `src/ariadne/sqlite_store.py` defines `SqliteGraphStore` satisfying the
      existing `GraphStore` protocol with **no protocol changes** and **no new
      dependencies**
- [ ] Schema:
      ```sql
      CREATE TABLE nodes(
          id TEXT PRIMARY KEY, type TEXT NOT NULL,
          properties TEXT NOT NULL, evidence_ids TEXT NOT NULL);
      CREATE TABLE edges(
          type TEXT NOT NULL,
          source TEXT NOT NULL REFERENCES nodes(id),
          target TEXT NOT NULL REFERENCES nodes(id),
          evidence_ids TEXT NOT NULL);
      CREATE INDEX edges_source ON edges(source);
      CREATE INDEX edges_target ON edges(target);
      CREATE INDEX nodes_type   ON nodes(type);
      ```
      created idempotently (`IF NOT EXISTS`) so reopening an existing DB is a no-op
- [ ] `properties` / `evidence_ids` are JSON columns written and read via the
      existing `node_to_dict` / `node_from_dict` / `edge_to_dict` /
      `edge_from_dict` helpers — one serialization path, lossless round-trip
- [ ] `edges` is **not** unique on `(source, target)`: two differently-typed
      edges between the same pair must both survive
- [ ] `add_node` upserts, matching `InMemoryGraphStore`'s dict-assignment semantics
- [ ] `add_edge` raises on a missing source/target with the **same error message**
      as `InMemoryGraphStore`, enforced in Python (SQLite foreign keys are off by
      default — do not rely on the `REFERENCES` clause)
- [ ] `save()` / `load()` remain JSON export/import, so existing fixtures, the
      gold graph and the eval harness interoperate unchanged
- [ ] `tests/ariadne/test_graph_store.py` is parametrized over both backends, so
      the protocol suite becomes the conformance suite; SQLite cases use `tmp_path`
- [ ] One additional test the in-memory store cannot express: close and reopen
      the DB, confirm the graph is still there
- [ ] `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` pass

## Notes

CLI wiring is task 0024 — this task ends with the backend plus its tests.

`neighbors()` should use the `edges_source` / `edges_target` indexes; this is
the real win over the in-memory list scan and helps the known-slow O(V·E)
`what_happens`.
