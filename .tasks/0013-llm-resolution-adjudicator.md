---
status: todo
priority: high
owner:
created: 2026-07-16
updated: 2026-07-16
---

# LLM resolution adjudicator (ambiguity-band seam)

## Description

Rule-based fuzzy matching can't decide borderline cases ("Warehouse Team" vs
"Fulfillment Crew" — same team, zero lexical overlap; "Order System" vs
"Ordering Policy System" — different things). Add a `ResolutionAdjudicator`
seam mirroring the `ExtractionProvider` pattern in `extraction.py`:

- `ResolutionAdjudicator` protocol: `same_entity(node_a, node_b) -> bool`
  (given the two nodes' type, labels, properties, and evidence excerpts).
- `FakeAdjudicator` for tests (canned verdicts), `AnthropicAdjudicator` for live.
- `resolve(store, adjudicator=None)`: pairs scoring in an ambiguity band
  (below auto-merge threshold, above clearly-distinct floor) are sent to the
  adjudicator; without one, ambiguous pairs stay unmerged (conservative default
  — a wrong merge is worse than a missed one).

## Acceptance Criteria

- [ ] Pairs above the auto-merge threshold never hit the adjudicator
- [ ] Pairs in the ambiguity band are adjudicated; verdict decides the merge
- [ ] Without an adjudicator, ambiguous pairs stay unmerged (conservative)
- [ ] `AnthropicAdjudicator` exists but tests only use the fake (no live calls)
- [ ] `uv run pytest` and `uv run ruff check .` pass

## Notes

Dependencies: 0012. Same mock-first pattern as extraction — live quality gets
measured separately when an API key is available.
