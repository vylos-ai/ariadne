---
status: todo
priority: medium
owner:
created: 2026-07-16
updated: 2026-07-16
---

# `ariadne export` — mermaid projection

## Description

Phase 4 slice: on-demand mermaid flowchart rendered from any graph.json —
projection, never stored as primary artifact. New module
`src/ariadne/export.py` + `ariadne export <graph.json> [--format mermaid]`
printing to stdout (redirectable):

- Flowchart of `ProcessStep`/`Decision`/`Exception` nodes connected by
  `triggers` edges; decisions as diamonds.
- `Role` ownership shown via `owned_by` (subgraph per role — poor-man's
  swimlane), `System`/`DataObject` attached via `requires`/`produces`.
- `Evidence` nodes and `evidenced_by` edges excluded from the diagram (they
  are provenance, not process).
- Node labels escaped/sanitized so arbitrary extracted text can't break
  mermaid syntax.
- Deterministic output: same graph → identical diagram text.

## Acceptance Criteria

- [ ] `ariadne export tests/fixtures/returned_order/gold_graph.json` emits valid mermaid
- [ ] Decisions render as diamonds; steps grouped by owning role
- [ ] Evidence nodes/edges never appear in the output
- [ ] Labels with quotes/brackets/newlines are safely escaped
- [ ] Output is deterministic
- [ ] `uv run pytest` and `uv run ruff check .` pass

## Notes

Dependencies: 0003, 0005. A throwaway generator from a previous session proved
the rendering looks good — this is the real, tested version. BPMN-XML export
stays out of scope until someone asks for it.
