---
status: done
priority: high
owner:
created: 2026-07-16
updated: 2026-07-16
---

# Entity resolution core (deterministic pass)

## Description

New module `src/ariadne/resolution.py`: `resolve(store) -> InMemoryGraphStore`
that collapses duplicate nodes describing the same entity across sources into
canonical nodes. Deterministic, rule-based first pass (no LLM — that seam is
0013):

- Candidate pairs: same `NodeType` + fuzzy label match (reuse the label/fuzzy
  logic pattern from `eval.py`; extract shared helpers rather than duplicating).
- Merge: canonical node keeps a deterministic id (lexicographically smallest of
  the cluster), unions `evidence_ids`, merges `properties` (first non-empty
  value wins per key; losing labels recorded under an `aliases` property).
- Edges are rewritten to canonical ids; duplicate edges (same type/source/target)
  are deduped with their `evidence_ids` unioned — an edge seen in two sources is
  *better* evidenced, not repeated.
- `Evidence` nodes are never merged (each source is distinct provenance).

## Acceptance Criteria

- [ ] Two nodes with same type + near-identical labels merge into one canonical node
- [ ] Merged node unions evidence_ids and records losing labels as `aliases`
- [ ] Edges are rewritten to canonical ids; duplicate edges dedupe with evidence unioned
- [ ] Nodes of different types never merge, Evidence nodes never merge
- [ ] Resolution is deterministic: same input graph → identical output graph
- [ ] Resolved graph passes provenance validation
- [ ] `uv run pytest` and `uv run ruff check .` pass

## Notes

Dependencies: 0002, 0003. No new node/edge types — merge lineage lives in
`properties["aliases"]` + evidence union. This is the hardest and most
important Phase 2 piece per CLAUDE.md.
