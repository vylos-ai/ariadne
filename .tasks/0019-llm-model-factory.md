---
status: todo
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

- [ ] `src/ariadne/llm.py` exposes `build_model(...)` reading env, with explicit
      keyword args taking precedence:
      - `ARIADNE_LLM_MODEL` — model name
      - `ARIADNE_LLM_BASE_URL` — OpenAI-compatible endpoint (unset ⇒ native path)
      - `ARIADNE_LLM_API_KEY` — key for that endpoint
- [ ] base URL set → returns
      `OpenAIChatModel(name, provider=OpenAIProvider(base_url=..., api_key=...))`
- [ ] base URL unset → returns the provider-prefixed model string unchanged
      (e.g. `"anthropic:claude-opus-4-8"`), so the existing `ANTHROPIC_API_KEY`
      flow keeps working
- [ ] Default when nothing is set: `anthropic:claude-opus-4-8`
- [ ] `pyproject.toml`: `anthropic` dropped; `pydantic-ai-slim[openai,anthropic]`
      and `logfire` added
- [ ] Tests cover the env matrix (nothing set / model only / base URL + key /
      explicit-arg override) and assert on the constructed object or string —
      **no network calls**
- [ ] `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` pass

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
