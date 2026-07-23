---
status: done
priority: medium
owner:
created: 2026-07-23
updated: 2026-07-23
---

# Store factory + CLI wiring for the SQLite backend

## Description

`SqliteGraphStore` (task 0023) is unreachable from the command line: every CLI
subcommand hardcodes `InMemoryGraphStore()` + `.load()`. Add a small factory
that picks a backend from the path, and route the CLI through it, so the same
commands work against a `.db` and a `.json` with identical output.

Also record the backend decision in the docs — `graph_store.py`'s module
docstring and CLAUDE.md's open question both still point at Kùzu, which was
archived by its vendor in October 2025.

## Acceptance Criteria

- [x] `graph_store.open_store(path) -> GraphStore`: a `.db` / `.sqlite` suffix
      opens `SqliteGraphStore`; a `.json` file opens `InMemoryGraphStore` +
      `load()`
- [x] The `InMemoryGraphStore()` + `.load()` pairs in `cli.py` (`_validate`,
      `_resolve`, `_query`, `_export`, `_mcp`) go through `open_store()`
- [x] `pipeline.py` and `resolution.py` still build in-memory stores for
      computation and write out via `save()` — no behaviour change there
- [x] Every subcommand produces byte-identical output for a `.db` and the
      equivalent `.json` (covered by a test, not just by hand)
- [x] `graph_store.py` module docstring no longer describes a "Kùzu seam"; it
      names SQLite and why
- [x] CLAUDE.md's graph-store open question records the decision: Kùzu archived
      2025-10, traversal is app-side so no Cypher engine is needed, SQLite chosen
- [x] `HOW_TO_TEST.md` §2 gains the SQLite path: import the gold graph into a
      `.db`, then run `validate` / `query` / `export` against it
- [x] `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` pass

## Notes

Suffix inference keeps five subcommands flag-free (YAGNI). Add an explicit
`--backend` flag only if inference turns out to be ambiguous in practice — do
not add it pre-emptively.

## Review outcome

Approved. Notable: the byte-identical parity test written for this task
exposed a latent ordering bug in `SqliteGraphStore` from task 0023 --
`neighbors()`, `by_type()` and `save()` had no `ORDER BY rowid`, so SQLite's
OR-optimizer could return rows out of insertion order. 0023's parametrized
conformance suite missed it because it compared return values rather than
rendered output. For a tool whose entire output surface is generated
projections, ordering is correctness.
