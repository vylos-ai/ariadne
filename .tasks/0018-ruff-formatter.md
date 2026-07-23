---
status: done
priority: medium
owner:
created: 2026-07-23
updated: 2026-07-23
---

# Adopt the ruff formatter project-wide

## Description

`ruff format` is listed in CLAUDE.md's verification commands but is not
configured or enforced, so style can drift between subagent-authored files.
Pin the formatter conventions in `pyproject.toml`, format the repo once as a
behaviour-neutral change, and add `ruff format --check` to the verification
loop so later tasks fail loudly on unformatted code.

This lands first so every subsequent diff in this batch is style-stable.

## Acceptance Criteria

- [x] `pyproject.toml` has a `[tool.ruff.format]` section pinning
      `quote-style = "double"`, `indent-style = "space"`, `line-ending = "lf"`
      (`line-length = 88` already exists under `[tool.ruff]` and is shared)
- [x] `uv run ruff format .` has been run across `src/`, `tests/`, `scripts/`
- [x] `uv run ruff format --check .` passes
- [x] `uv run ruff check .` passes
- [x] `uv run pytest` still passes (170 tests) — formatting is behaviour-neutral
- [x] CLAUDE.md "Verification commands" lists `uv run ruff format --check .`
- [x] `HOW_TO_TEST.md` §1 lists `uv run ruff format --check .`

## Notes

No test is written for this task — it is a tooling/config change with no
runtime behaviour, so the TDD red/green cycle does not apply. The existing
suite staying green is the regression gate.

Keep this commit formatting-only: no behavioural edits mixed in.
