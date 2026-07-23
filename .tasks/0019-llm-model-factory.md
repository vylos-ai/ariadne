---
status: done
priority: high
owner:
created: 2026-07-23
updated: 2026-07-23
---

# LLM model factory (`llm.py`) + Pydantic AI dependency swap

## Description

`extraction.py` and `resolution.py` each construct `anthropic.Anthropic()`
directly and pin the stale model id `claude-sonnet-4-5-20250929`. There is no
way to point Ariadne at a local model (Ollama), another provider, or another
Anthropic model without editing source.

Introduce `src/ariadne/llm.py` as the single place a model is configured, built
on Pydantic AI. Goal: swap the LLM by changing **only** a base URL, API key and
model name. This task adds the seam and the dependency swap; callers are ported
in 0020 / 0021.

## Acceptance Criteria

- [x] `src/ariadne/llm.py` exposes `build_model(...)` reading env, with explicit
      keyword args taking precedence:
      - `ARIADNE_LLM_MODEL` — model name
      - `ARIADNE_LLM_BASE_URL` — OpenAI-compatible endpoint (unset ⇒ native path)
      - `ARIADNE_LLM_API_KEY` — key for that endpoint
- [x] base URL set → returns
      `OpenAIChatModel(name, provider=OpenAIProvider(base_url=..., api_key=...))`
- [x] base URL unset → returns the provider-prefixed model string unchanged
      (e.g. `"anthropic:claude-opus-4-8"`), so the existing `ANTHROPIC_API_KEY`
      flow keeps working
- [x] Default when nothing is set: `anthropic:claude-opus-4-8`
- [x] `pyproject.toml`: `anthropic` dropped; `pydantic-ai-slim[openai,anthropic]`
      and `logfire` added
- [x] Tests cover the env matrix (nothing set / model only / base URL + key /
      explicit-arg override) and assert on the constructed object or string —
      **no network calls**
- [x] `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` pass

## Notes

Verified API surface (do not re-derive):

```python
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel   # NOT OpenAIModel (renamed)
from pydantic_ai.providers.openai import OpenAIProvider

model = OpenAIChatModel(name, provider=OpenAIProvider(base_url=..., api_key=...))
agent = Agent(model, output_type=SomeModel, instructions="…")
result = agent.run_sync(prompt)   # result.output is the validated model
```

The OpenAI-compatible path covers Ollama (`http://localhost:11434/v1`),
OpenRouter, vLLM and LM Studio.

Don't port `extraction.py` / `resolution.py` here — that is 0020 / 0021. This
task ends with `llm.py` + tests + deps only.

`anthropic` was removed as a direct dependency in `pyproject.toml` per the
acceptance criteria, but the `anthropic` SDK package is still installed
transitively via the `pydantic-ai-slim[anthropic]` extra, so `extraction.py`
and `resolution.py` (which do `import anthropic` directly) continue to work
unmodified. 0020/0021 should port those modules to `build_model()` and can
then drop the `anthropic` extra from `pydantic-ai-slim[...]` if no longer
needed.

Fix after first review pass: `build_model()` previously resolved `model` to
the `anthropic:claude-opus-4-8` default *before* checking `base_url`, so a
user setting only `ARIADNE_LLM_BASE_URL` (+ key) and forgetting
`ARIADNE_LLM_MODEL` would silently ship a provider-prefixed name to an
OpenAI-compatible endpoint that has no concept of the `anthropic:` prefix,
failing opaquely at request time. Now, when `base_url` is set and no
explicit model was given (neither `model` kwarg nor `ARIADNE_LLM_MODEL`),
`build_model()` raises `ValueError` naming `ARIADNE_LLM_MODEL` at
construction time instead of falling back to the default or attempting any
prefix-stripping.
