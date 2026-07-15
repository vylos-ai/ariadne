---
status: done
priority: high
owner:
created: 2026-07-15
updated: 2026-07-15
---

# Provenance validator (`ariadne validate`)

## Description

Implement `ariadne validate <graph>`: enforce the trust boundary — every edge and
every non-trivial node property must point to an Evidence node. Report violations
and exit non-zero on failure. Expose the check as a reusable library function so
the extraction pipeline (0008) and the Phase 1 baseline (0010) can call it.

## Acceptance Criteria

- [ ] `validate(graph)` returns a list of provenance violations (unevidenced edges/props)
- [ ] `ariadne validate <graph>` prints violations and exits non-zero when any exist
- [ ] The Phase 0 gold graph passes with zero violations
- [ ] A deliberately unevidenced edge is reported
- [ ] `uv run pytest` and `uv run ruff check .` pass

## Notes

Dependencies: 0002, 0005.
This is the ground-truth gate: an ungrounded graph is worse than none (CLAUDE.md).
