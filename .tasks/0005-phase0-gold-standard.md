---
status: done
priority: critical
owner:
created: 2026-07-15
updated: 2026-07-15
---

# Phase 0 gold standard ("returned order" process)

## Description

Hand-build the Phase 0 gold standard for the "how do we handle a returned order"
process — the reference for "what good looks like" before any extraction code is
trusted. Author 2–3 messy source documents (e.g. two emails + a short interview
transcript) as fixtures, and a human-authored canonical graph (in the 0003 JSON
format) with full provenance back to those docs, rendered to a committed reference
vault. No extraction here — this is human-authored ground truth.

## Acceptance Criteria

- [ ] `tests/fixtures/returned_order/` holds 2–3 messy source documents
- [ ] A hand-authored gold graph (JSON) captures the process, exercising every node type used and linking Evidence to the source docs
- [ ] The gold graph loads through `GraphStore` without errors
- [ ] The gold graph renders to a committed reference vault via 0004
- [ ] Every edge in the gold graph has an Evidence reference; a test asserts this
- [ ] `uv run pytest` and `uv run ruff check .` pass

## Notes

Dependencies: 0002, 0003, 0004.
Keep the process small but realistic. This graph is the yardstick the eval harness
(0006) and Phase 1 baseline (0010) measure against — invest in getting it right.
