---
status: todo
priority: medium
owner:
created: 2026-07-15
updated: 2026-07-15
---

# Phase 1 baseline eval (extract → validate → eval, offline)

## Description

Tie the Phase 1 loop together: extract the Phase 0 source docs (using recorded or
fake provider output so it runs offline), validate provenance, and eval the result
against the gold standard to record a committed baseline score. This guards against
regressions as extraction quality improves and demonstrates the full core loop
end-to-end.

## Acceptance Criteria

- [ ] A test/script runs `extract` over the Phase 0 sources and evals against the gold graph
- [ ] The extracted graph passes provenance validation (0009)
- [ ] Baseline P/R/F1 numbers are committed as the regression reference
- [ ] The whole run is offline (recorded/fake provider output, no network)
- [ ] `uv run pytest` and `uv run ruff check .` pass

## Notes

Dependencies: 0006, 0008, 0009.
This closes Phase 1. Phase 2 (entity resolution) and beyond are planned separately
once this baseline is in place.
