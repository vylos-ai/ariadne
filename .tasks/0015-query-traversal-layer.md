---
status: done
priority: medium
owner:
created: 2026-07-16
updated: 2026-07-16
---

# Query/traversal layer + `ariadne query`

## Description

Phase 3 core: a small library of graph questions an agent (or human) can ask,
exposed as `ariadne query <graph.json> <question-type> [args]`. New module
`src/ariadne/query.py` operating on any `GraphStore`:

- `find_nodes(store, text)` — fuzzy label lookup (reuse shared label helpers),
  returns matching nodes ranked by score.
- `describe(store, node_id)` — node + all its edges with the neighbor labels
  and the evidence behind each fact.
- `walk(store, node_id, edge_type=None, direction=...)` — one-hop neighbors.
- `path(store, from_id, to_id)` — shortest path over typed edges (BFS), for
  "how does X lead to Y" questions.
- `what_happens(store, node_id)` — downstream closure over
  `triggers`/`produces` edges: "what happens after X".

Every answer must carry the evidence ids that ground it — an agent answer
without provenance violates the trust boundary.

## Acceptance Criteria

- [ ] All five query functions work against the Phase 0 gold graph in tests
- [ ] Answers include the evidence ids grounding each returned fact
- [ ] `ariadne query` subcommand prints human-readable results for each question type
- [ ] Unknown node ids / no-path cases return empty results, not exceptions
- [ ] `uv run pytest` and `uv run ruff check .` pass

## Notes

Dependencies: 0003, 0005. Vector search is deliberately out of scope for this
task (YAGNI until fuzzy label lookup proves insufficient) — graph traversal
first, hybrid retrieval later.
