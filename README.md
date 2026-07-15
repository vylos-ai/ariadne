# Ariadne — Process Layer

An AI-native process knowledge system for companies whose processes are **not**
cleanly instrumented in an ERP/event log. Unlike classical process mining
(Celonis, SAP Signavio, ARIS), which reconstructs process graphs from clean,
timestamped system event logs, Ariadne builds process graphs from **messy,
human-generated sources**: emails, Slack/Teams threads, spreadsheets, interview
transcripts, meeting notes, tribal knowledge.

Core bet: **the graph is the source of truth. Every visualization (BPMN,
swimlane, Gantt, slide, markdown doc) is a projection generated on demand,
never hand-maintained.**

See [`CLAUDE.md`](./CLAUDE.md) for the full project brief — architecture, node/
edge schema, pipeline, implementation phases, and open questions.

## Development workflow

Ariadne uses an agentic TDD workflow (Python 3.12+). Every change goes through a
red/green cycle enforced by two subagents:

1. **`tdd`** — writes a failing test, implements minimal code to pass it, runs
   pytest + ruff, then hands off for review.
2. **`reviewer`** — read-only review (correctness, security, test coverage,
   YAGNI) on a lighter model in a cleared context. Returns a `VERDICT:`; the
   orchestrator applies it (`review` → `done`).

Tasks are tracked as markdown files in `.tasks/` with YAML frontmatter, moving
through `backlog` → `todo` → `in-progress` → `review` → `done`. See
`.tasks/_template.md` for the schema.

## Getting started

```bash
uv sync --group dev        # Install dependencies
```

Create your first task in `.tasks/0001-your-task.md` (see `.tasks/_template.md`),
then start the TDD workflow by delegating to the `tdd` subagent.

## Verification

```bash
uv run pytest                       # Run tests
uv run ruff check .                 # Lint
uv run ruff format .                # Format
python scripts/kanban.py --simple   # Task board (plain text)
python scripts/kanban.py            # Task board (live TUI)
```

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) for dependency management
