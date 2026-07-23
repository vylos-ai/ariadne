---
status: done
priority: high
owner:
created: 2026-07-23
updated: 2026-07-23
---

# `ariadne serve` — local web server + JSON API

## Description

The system is hard to inspect and feels abstract: today the only way to look at
a graph is CLI subcommands one node at a time. A local web UI makes it concrete
and, more importantly, makes it *testable* — the point is the "is this actually
right?" loop, where every node and edge is one click from its evidence and the
verbatim source text it came from.

This task is the backend half: an HTTP server and a JSON API over an existing
graph. The browser UI is task 0026.

`starlette` and `uvicorn` are already installed transitively via `mcp`, so this
costs no new resolved dependencies — but declare both explicitly in
`pyproject.toml` rather than relying on a transitive import.

## Acceptance Criteria

- [x] `src/ariadne/web.py` builds a Starlette app via `build_app(store)`,
      mirroring how `mcp_server.py::build_server(store)` takes an already-open
      store — the app must not know which backend it got
- [x] `ariadne serve <graph> [--host] [--port]` opens the graph with
      `open_store()` (so `.json`, `.db` and `.sqlite` all work) and runs uvicorn
- [x] `GET /api/graph` → all nodes and edges, plus per-type counts for the
      sidebar. Evidence nodes are included but flagged so the UI can separate
      provenance from process content.
- [x] `GET /api/nodes/{id}` → the node plus **every incident fact**, reusing
      `query.describe()` — do not reimplement traversal. Each fact carries its
      edge type, direction, neighbor id, neighbor label and `evidence_ids`.
      Unknown id → 404 with a JSON error body, not a stack trace.
- [x] `GET /api/evidence/{id}` → the Evidence node's verbatim `text` and
      `source` properties. This is the endpoint the trust loop depends on: it
      is what lets a human check a claim against what was actually written.
      Unknown id → 404.
- [x] `GET /api/mermaid` → the mermaid source from the existing
      `export.to_mermaid()`, so the UI renders the same projection the CLI emits
- [x] Tests use `starlette.testclient.TestClient` (httpx is already installed).
      Cover every endpoint including both 404 paths, and assert the API is
      backend-neutral by running the same assertions against a `.json`-loaded
      store and a `SqliteGraphStore` — reuse the parametrized approach from
      `test_graph_store.py`.
- [x] `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` pass

## Notes

Read-only for now. No mutation endpoints — corrections-as-evidence is Phase 5
and needs the supersede/temporal model designed first; adding write endpoints
before that would bake in the wrong shape.

Serve on localhost by default. This is an internal inspection tool holding
possibly-sensitive process knowledge, so it should not bind 0.0.0.0 unless the
user explicitly passes `--host`.

## Review outcome

Approved. Also fixed a latent bug this task surfaced: `sqlite3.connect` needed
`check_same_thread=False`, because ASGI dispatches requests on worker threads
other than the one that opened the store. Verified safe rather than assumed --
`sqlite3.threadsafety == 3` (serialized), so sharing a connection across
threads is permitted, and the web API has no write path that could race.
Revisit if mutation endpoints are ever added (Phase 5).
