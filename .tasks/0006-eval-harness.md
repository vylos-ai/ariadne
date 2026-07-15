---
status: todo
priority: high
owner:
created: 2026-07-15
updated: 2026-07-15
---

# Eval harness (precision/recall/F1 + grounding vs gold)

## Description

Lightweight quality measurement of a candidate graph against the Phase 0 gold
graph: precision/recall/F1 over typed nodes and typed edges (with fuzzy label
matching), plus an evidence-grounding coverage metric. Runnable both as pytest and
as `ariadne eval`. This must exist before extraction quality is ever measured, so
regressions are caught early rather than bolted on later.

## Acceptance Criteria

- [ ] Node P/R/F1 computed by `(type, fuzzy-matched label)` against gold
- [ ] Edge P/R/F1 computed by `(type, matched endpoints)` against gold
- [ ] Grounding metric reports the fraction of candidate edges/properties carrying evidence refs
- [ ] `ariadne eval <candidate> <gold>` prints the metrics
- [ ] Feeding the gold graph as its own candidate yields P=R=F1=1.0 and 100% grounding
- [ ] `uv run pytest` and `uv run ruff check .` pass

## Notes

Dependencies: 0002, 0003, 0005.
Keep matching simple (normalized/fuzzy label compare) — YAGNI; no ML matcher yet.
