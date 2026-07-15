---
status: done
priority: high
owner:
created: 2026-07-15
updated: 2026-07-15
---

# Extraction pipeline CLI (`ariadne extract`)

## Description

Implement `ariadne extract <source>`: run the extraction provider over a source
document, create an Evidence node for the source, build nodes/edges **with
provenance from the start** (every edge points to the Evidence), write the result
to the graph store, and materialize the vault. Provenance is wired in here, not
bolted on later.

## Acceptance Criteria

- [ ] `ariadne extract <file>` produces a graph JSON + vault directory on disk
- [ ] Each source doc becomes an Evidence node; every extracted edge references it
- [ ] End-to-end test runs with the fake provider (no network)
- [ ] Given identical provider output, the run is deterministic
- [ ] The output graph loads through `GraphStore` and passes provenance checks
- [ ] `uv run pytest` and `uv run ruff check .` pass

## Notes

Dependencies: 0007, 0003, 0004.
Entity resolution across multiple sources is a later phase — this task handles a
single source doc.
