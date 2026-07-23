---
status: done
priority: medium
owner:
created: 2026-07-23
updated: 2026-07-23
---

# Logfire observability + LLM configuration docs

## Description

With extraction and resolution running through Pydantic AI, add opt-in Logfire
tracing so live runs are inspectable (which prompt, which model, what came
back), and document how to point Ariadne at different providers.

This is the payoff of tasks 0019–0021: running the same eval against several
models by changing only environment variables.

## Acceptance Criteria

- [x] `llm.configure_observability()` calls `logfire.configure()` and
      `logfire.instrument_pydantic_ai()`
- [x] It is **opt-in and failure-tolerant**: a no-op unless `LOGFIRE_TOKEN` or
      `ARIADNE_TRACE=1` is set, and never raises or blocks if Logfire is
      unreachable — offline runs and the test suite must emit nothing
- [x] Called once from `cli.main()`
- [x] `.env.example` committed with `ARIADNE_LLM_MODEL`, `ARIADNE_LLM_BASE_URL`,
      `ARIADNE_LLM_API_KEY`, `LOGFIRE_TOKEN`, showing three worked profiles:
      Anthropic native, Ollama local, OpenRouter
- [x] `.env.example` contains no real credentials; `.env` stays gitignored
- [x] `HOW_TO_TEST.md` §5 rewritten as a provider-parameterised live loop
      (extract → validate → resolve → eval), with a note on running the same
      eval against N models and comparing node/edge F1
- [x] `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` pass

## Notes

Verified API: `logfire.configure()` then `logfire.instrument_pydantic_ai()`.

The live comparison itself is run by the user with their own credentials — this
task ships the tooling and the documented commands, not the measurement.
