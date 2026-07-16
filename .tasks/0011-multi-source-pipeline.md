---
status: done
priority: high
owner:
created: 2026-07-16
updated: 2026-07-16
---

# Multi-source extraction pipeline

## Description

Extend the extraction pipeline so `ariadne extract` accepts multiple source
documents and produces **one merged, unresolved graph**. Each source document
becomes its own `Evidence` node (content-hash id, as today), and every node/edge
extracted from a source is grounded in that source's evidence node. Extracted
node ids must be namespaced per source (e.g. prefix with a short source hash) so
two documents that each produce `role-support` don't silently collide — leaving
duplicates in the graph is *correct* at this stage; entity resolution (0012)
collapses them.

## Acceptance Criteria

- [ ] `run_extraction_pipeline` accepts a list of source paths (single path keeps working)
- [ ] Each source gets its own `Evidence` node; extracted edges from a source reference it
- [ ] Node ids from different sources cannot collide (namespaced), so duplicates survive as distinct nodes
- [ ] `ariadne extract src1.txt src2.txt --output-dir out` writes one merged graph.json + vault
- [ ] Merged graph passes `ariadne validate` with zero violations
- [ ] `uv run pytest` and `uv run ruff check .` pass

## Notes

Dependencies: 0008. This is the precondition for Phase 2 — resolution needs a
multi-document graph with duplicates to collapse. Use FakeExtractionProvider in
tests; no live API calls.
