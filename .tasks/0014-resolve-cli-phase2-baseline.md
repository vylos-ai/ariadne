---
status: todo
priority: high
owner:
created: 2026-07-16
updated: 2026-07-16
---

# `ariadne resolve` CLI + Phase 2 baseline eval

## Description

Wire resolution into the CLI and close the Phase 2 loop against the gold
standard, mirroring how 0010 closed Phase 1:

- `ariadne resolve <graph.json> --output-dir out`: load graph, run
  `resolve()`, write resolved graph.json + regenerated vault.
- Phase 2 baseline (extend `baseline.py` or add alongside): offline
  multi-source extract (all three returned-order fixtures, fake provider) →
  resolve → eval vs `gold_graph.json`. Assert resolution strictly reduces
  duplicate nodes and node precision/F1 does not regress vs the unresolved
  graph; persist metrics as a regression fixture like
  `baseline_metrics.json`.

## Acceptance Criteria

- [ ] `ariadne resolve` writes a resolved graph + vault; resolved graph passes `ariadne validate`
- [ ] Baseline test: multi-source extract → resolve → eval runs fully offline
- [ ] Resolved metrics ≥ unresolved metrics on node F1; duplicate count drops
- [ ] Metrics persisted as a committed regression fixture
- [ ] `uv run pytest` and `uv run ruff check .` pass

## Notes

Dependencies: 0011, 0012, 0013. This is the "checked against the Phase 0
gold-standard graph before moving on" gate for Phase 2.
