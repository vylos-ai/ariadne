---
status: done
priority: high
owner:
created: 2026-07-15
updated: 2026-07-15
---

# Package scaffold (src/ariadne layout + CLI entry point)

## Description

Adopt a `src/ariadne/` layout and make the package installable with a console
entry point, so the product code lives in a proper package separate from the
`scripts/kanban.py` dev tooling. Add a `[build-system]` (hatchling) and
`[project.scripts] ariadne = "ariadne.cli:main"` to `pyproject.toml`; create
`src/ariadne/__init__.py` (with `__version__`) and a `cli.py` stub that dispatches
subcommands (`extract`, `eval`, `validate` — stubs for now). Mirror tests under
`tests/ariadne/`. `scripts/kanban.py` and its tests are untouched.

## Acceptance Criteria

- [x] `pyproject.toml` has a `[build-system]` (hatchling) and `uv sync` installs the package editable
- [x] `import ariadne` works and exposes `__version__`
- [x] `ariadne` console script is registered; `ariadne --help` runs and lists subcommands (stubs OK)
- [x] `tests/ariadne/` exists with a smoke test asserting the version imports
- [x] `uv run pytest` and `uv run ruff check .` pass

## Notes

Dependencies: none (first task).
Layout: product code in `src/ariadne/`; tests mirror under `tests/ariadne/`.
Do not modify `scripts/kanban.py`.
