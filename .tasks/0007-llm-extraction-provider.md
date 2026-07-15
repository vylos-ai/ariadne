---
status: done
priority: high
owner:
created: 2026-07-15
updated: 2026-07-15
---

# LLM extraction provider (Anthropic, mockable)

## Description

Add the `anthropic` dependency and define a mockable `ExtractionProvider`
interface: given source text plus the node/edge schema as hints, return candidate
nodes/edges with evidence spans. Wrap the Claude API behind the interface with a
fake implementation for offline tests (no network in CI). Centralize the model id
in a single config constant; the exact model choice is deferred to implementation.

## Acceptance Criteria

- [ ] `anthropic` added to `pyproject.toml`; a single `MODEL` constant holds the model id
- [ ] `ExtractionProvider` interface defines `extract(text)` → candidate nodes/edges with evidence
- [ ] A fake provider returns canned schema-conforming output for tests (no network)
- [ ] The real provider builds a tool-use request using the node/edge schema as hints, unit-tested via a mocked client (no live call)
- [ ] Extraction output validates against the 0002 schema
- [ ] `uv run pytest` and `uv run ruff check .` pass

## Notes

Dependencies: 0001, 0002.
Schema is used as *hints*, not rigid constraints (CLAUDE.md), to avoid false
categorization. No live API calls in tests — always go through the fake/mock.
