---
status: todo
priority: medium
owner:
created: 2026-07-16
updated: 2026-07-16
---

# MCP server exposing query tools

## Description

Phase 3 delivery: expose the 0015 query layer as MCP tools so a
general-purpose agent (Claude etc.) can answer process questions grounded in
the graph. New module `src/ariadne/mcp_server.py` + `ariadne mcp <graph.json>`
subcommand that serves stdio MCP with tools mapping 1:1 onto the query layer
(`find_nodes`, `describe`, `walk`, `path`, `what_happens`). Tool results are
JSON and always include the grounding evidence ids.

Add the official `mcp` Python SDK as a dependency. Tests exercise the tool
handler functions directly (register + call handlers in-process) — no
subprocess/stdio integration test needed for v1.

## Acceptance Criteria

- [ ] `mcp` dependency added; `ariadne mcp <graph.json>` starts a stdio server
- [ ] All five query tools are registered with descriptions + JSON schemas
- [ ] Tool handlers return JSON results incl. evidence ids (tested in-process against the gold graph)
- [ ] `uv run pytest` and `uv run ruff check .` pass

## Notes

Dependencies: 0015. First new runtime dependency since scaffold — deliberate,
it IS the Phase 3 deliverable ("expose as MCP server", CLAUDE.md).
