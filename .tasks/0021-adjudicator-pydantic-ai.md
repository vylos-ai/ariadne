---
status: done
priority: high
owner:
created: 2026-07-23
updated: 2026-07-23
---

# Port the resolution adjudicator to Pydantic AI + wire `--adjudicate`

## Description

`AnthropicAdjudicator` in `resolution.py` calls the Anthropic SDK directly,
pins the stale model id, and parses a free-text yes/no answer. Replace it with
a provider-agnostic `PydanticAIAdjudicator` returning a structured verdict.

Also wire the ambiguity-band adjudicator into the CLI: `_resolve()` currently
calls `resolve(store)` with no adjudicator, so the seam built in task 0013 has
never been reachable from the command line.

## Acceptance Criteria

- [x] `PydanticAIAdjudicator` implements the existing `ResolutionAdjudicator`
      protocol and uses `output_type=SameEntityVerdict` (a `BaseModel` with
      `same_entity: bool` and `reason: str`) instead of parsing free text
- [x] `AnthropicAdjudicator` and the `anthropic` import are removed from
      `resolution.py`
- [x] `ResolutionAdjudicator`, `FakeAdjudicator`, `AMBIGUITY_FLOOR` and the
      union-find clustering core are unchanged
- [x] `ariadne resolve --adjudicate` passes `PydanticAIAdjudicator()` into
      `resolve()`; without the flag, behaviour is byte-identical to today
      (conservative no-merge in the ambiguity band)
- [x] Tests cover: verdict `True` merges an ambiguity-band pair, verdict `False`
      does not, and the adjudicator is not consulted outside the band
      `[AMBIGUITY_FLOOR, 0.85)` — using pydantic-ai test doubles, no network
- [x] Phase 2 baseline metrics unchanged
- [x] `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` pass

## Notes

The `--adjudicate` flag spends API credits when used; it must stay opt-in and
default off, and no test may enable a real provider.
