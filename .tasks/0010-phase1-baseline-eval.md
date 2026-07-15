---
status: done
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

- [x] A test/script runs `extract` over the Phase 0 sources and evals against the gold graph
- [x] The extracted graph passes provenance validation (0009)
- [x] Baseline P/R/F1 numbers are committed as the regression reference
- [x] The whole run is offline (recorded/fake provider output, no network)
- [x] `uv run pytest` and `uv run ruff check .` pass

## Notes

Dependencies: 0006, 0008, 0009.
This closes Phase 1. Phase 2 (entity resolution) and beyond are planned separately
once this baseline is in place.

Implementation: chose option (b) -- a *recorded* provider payload derived
mechanically from `tests/fixtures/returned_order/gold_graph.json`, not the
generic `FakeExtractionProvider` canned example. For each of the three
Phase 0 source docs, `recorded_payload_for_source()` filters the gold graph
down to the nodes/edges whose `evidence_ids` reference that document's
Evidence node (plus any node needed as an edge endpoint), and feeds that
subset into `FakeExtractionProvider(payload)` -- still fully offline/
deterministic (no network), but grounded in the hand-authored gold standard
rather than an arbitrary unrelated payload.

`run_baseline()` (src/ariadne/baseline.py) runs `run_extraction_pipeline`
once per source doc (each pipeline call writes its own graph.json/vault
subdirectory, since the pipeline's contract is one call per source), then
merges the three resulting per-source graphs into a single combined
`InMemoryGraphStore`. `evaluate_baseline()` validates that merged graph
(`ariadne.validation.validate`) and evals it against the gold graph
(`ariadne.eval.evaluate`).

Recorded baseline (tests/fixtures/returned_order/baseline_metrics.json),
committed as the regression reference:
- Nodes: precision=0.889, recall=1.0, F1=0.941
- Edges: precision=1.0, recall=1.0, F1=1.0
- Grounding: 1.0
- Provenance violations: 0

The node precision is <1.0 for an honest, structural reason: each pipeline
run injects its own content-hashed source Evidence node (in addition to
whatever Evidence node(s) the provider returns), so the merged baseline
graph ends up with 3 extra Evidence nodes beyond gold's 3 hand-authored
ones -- these don't fuzzy-label-match gold (their label is the tmp source
file path, not gold's short doc name) and show up as false positives. This
is a known, deterministic artifact of the current pipeline design, not
extraction noise -- documented here rather than papered over.

New tests: tests/ariadne/test_baseline.py -- asserts zero provenance
violations, a nonempty extracted graph, run-to-run determinism, and that
P/R/F1/grounding match (and don't regress below) the committed reference.
