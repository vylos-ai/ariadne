---
status: todo
priority: high
owner:
created: 2026-07-15
updated: 2026-07-15
---

# Markdown vault serialization (graph → vault, deterministic)

## Description

Render each node to a markdown file: YAML frontmatter (structured properties +
provenance refs) + prose + `[[node-id]]` wiki links to related nodes, grouped by
edge type. Output must be **deterministic** — identical graph produces byte-identical
files (stable key/link ordering) so vault diffs are meaningful. Add a parse path
that reads a vault file back into a node dict, supporting the graph-canonical sync
model where human markdown edits are surfaced as diffs rather than silently
round-tripped.

## Acceptance Criteria

- [ ] A node renders to markdown with valid YAML frontmatter (`id`, `type`, properties, evidence refs)
- [ ] Related nodes render as `[[target-id]]` links grouped by edge type in the body
- [ ] Rendering is deterministic — same graph produces byte-identical output
- [ ] A vault file parses back into a node dict (frontmatter + links) for diffing
- [ ] Rendering a graph writes one file per node into a vault directory
- [ ] `uv run pytest` and `uv run ruff check .` pass

## Notes

Dependencies: 0002, 0003.
Sync direction is graph-canonical: vault is regenerated from the graph; the parse
path is for surfacing diffs, not for silent write-back.
