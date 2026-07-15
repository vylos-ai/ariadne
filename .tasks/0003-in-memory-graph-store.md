---
status: done
priority: high
owner:
created: 2026-07-15
updated: 2026-07-15
---

# In-memory graph store (GraphStore protocol + JSON impl)

## Description

Define a `GraphStore` protocol — the backend seam that Kùzu will later slot into —
and provide an in-memory/JSON reference implementation used for all of Phase 0–1.
Support CRUD for nodes/edges, typed neighbor lookup, query-by-type, and save/load
to a JSON file. This keeps Phase 0–1 dependency-light; the committed v1 backend
(Kùzu) is a later phase behind this same protocol.

## Acceptance Criteria

- [ ] `GraphStore` protocol/ABC defines `add_node`, `add_edge`, `get_node`, `neighbors`, `by_type`, `save`, `load`
- [ ] In-memory impl round-trips through JSON (`save` then `load`) with no data loss
- [ ] Adding an edge that references a missing node id is rejected/raises
- [ ] `neighbors` returns typed edges in both directions, filterable by edge type
- [ ] `uv run pytest` and `uv run ruff check .` pass

## Notes

Dependencies: 0002.
Do not pull in Kùzu/Neo4j here — the JSON impl is the reference backend for now.
