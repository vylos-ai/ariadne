# Process Layer — Project Brief for Claude Code

## What this is

An AI-native process knowledge system for companies whose processes are **not**
cleanly instrumented in an ERP/event log. Unlike classical process mining
(Celonis, SAP Signavio, ARIS), which reconstructs process graphs from clean,
timestamped system event logs, this tool builds process graphs from **messy,
human-generated sources**: emails, Slack/Teams threads, spreadsheets,
interview transcripts, meeting notes, screen recordings, tribal knowledge.

Target customer: mid-market / SMB companies that are too small, too
undigitized, or too cheap for Celonis-class tooling, but where "nobody fully
knows how our process actually works" is a real, expensive problem.

Core bet: **the graph is the source of truth. Every visualization (BPMN,
swimlane, Gantt, slide, markdown doc) is a projection generated on demand,
never hand-maintained.** The system optimizes first for AI-agent walkability,
second for human readability, and treats "pretty diagram" as a rendering
target, not a data model.

## Non-goals (explicitly out of scope for v1)

- Not competing with Celonis/Signavio on clean-ERP-log mining — assume no
  reliable event logs exist.
- Not building a general-purpose workflow automation/orchestration engine
  (n8n, Zapier already own that layer) — this is a *knowledge* layer, not an
  *execution* layer, though nodes should be able to carry action/tool
  bindings for future agent execution.
- Not a BPMN modeling tool. BPMN is one possible export, never the editing
  surface.
- v1 is not multi-tenant SaaS — build single-tenant / self-hostable first,
  prove the extraction + graph quality, worry about SaaS packaging later.

## Architecture

### Two-layer storage model

1. **Graph store (source of truth)** — nodes and typed edges, queryable and
   traversable. Start with a property graph (Neo4j, or Kùzu/SQLite-graph for
   a lighter self-hosted option — decide during setup, see Open Questions).
2. **Markdown vault (human + LLM projection)** — every node materializes as
   a markdown file with YAML frontmatter (structured properties) + prose +
   wiki-style links (`[[node-id]]`) to related nodes. Git-native, diffable,
   human-editable, and dual-purpose: it's both the documentation and the
   agent's retrieval context. Regenerated from the graph, or graph updated
   from edits to markdown (decide sync direction — see Open Questions).

Diagrams (BPMN-XML, mermaid, swimlane, slide deck) are generated on request
from a graph query result — never stored as the primary artifact.

### Node types (initial schema)

- `ProcessStep` — an activity/task in a process
- `Decision` — a branch point with conditions
- `Role` — a person, team, or job function
- `System` — a tool/software involved (SAP, Excel, Outlook, Slack, etc.)
- `DataObject` — an artifact created/consumed (invoice, PO, contract)
- `Exception` — a known deviation/edge case from the "happy path"
- `Policy` — a rule or constraint governing a decision
- `Evidence` — a provenance node: source document, email thread, transcript
  excerpt, ERP record, interview quote

### Edge types (initial schema)

`triggers`, `requires`, `produces`, `owned_by`, `escalates_to`,
`depends_on`, `contradicts`, `supersedes`, `evidenced_by`

### Provenance is first-class, not metadata

Every edge and every non-trivial node property must be traceable to an
`Evidence` node. No silent LLM inference gets written into the graph without
a pointer to what it was inferred from. This is the trust boundary that
makes the graph usable by an agent — an ungrounded process graph is worse
than none, because it looks authoritative.

### Temporal / reification

Processes change. Don't overwrite — supersede. A fact ("Step X is owned by
Role Y") is itself a node that can be superseded by a later fact, so the
graph can answer "what was true as of March" and "what changed and why."
This matters more here than in classical process mining, because a lot of
what's being captured is tribal knowledge that drifts ("we used to do it
this way until Maria left").

## Pipeline (draft v1 scope)

1. **Ingestion** — connectors for email export, Slack/Teams export, CSV/
   spreadsheet upload, plain interview transcripts (start with file upload,
   not live API integrations, to keep v1 small).
2. **Extraction** — LLM-based entity/relationship extraction into the node/
   edge schema above, using structured prompts with the schema as hints
   (not rigid constraints) to avoid false categorization.
3. **Entity resolution** — collapse duplicate/near-duplicate entities
   (same person, same document, same step described two ways) into
   canonical nodes. This is the hardest and most important step — expect
   to spend disproportionate effort here.
4. **Graph assembly** — write resolved nodes/edges + evidence pointers to
   the graph store; materialize/update the markdown vault.
5. **Query/traversal layer** — hybrid retrieval: graph traversal for
   multi-hop questions, vector search for fuzzy semantic lookup, exposed as
   tools an agent (or a human via chat) can call.
6. **Projection/export layer** — on-demand rendering to BPMN-XML, mermaid,
   markdown summary doc, slide outline.
7. **Human-in-the-loop review** — every extracted fact should be easy for a
   human to confirm/correct/reject before it's treated as ground truth;
   corrections should count as evidence too.

## Suggested implementation phases

**Phase 0 — Spike / prove the core loop**
Take one real, messy process (pick something small: "how do we handle a
returned order"), manually gather the source material, and hand-build the
target graph + markdown vault to define what "good" looks like before
writing extraction code.

**Phase 1 — Extraction MVP**
LLM extraction from a single source type (start with plain text transcripts
or emails) into the schema. No UI yet — CLI/script that outputs graph +
markdown vault to disk. Validate against the Phase 0 hand-built gold
standard.

**Phase 2 — Entity resolution**
Add resolution logic across multiple documents/sources for the same
process. This is where most of the engineering effort should go.

**Phase 3 — Query + agent tool interface**
Expose graph traversal + hybrid search as callable tools (e.g. MCP server)
so a general-purpose agent (Claude, etc.) can answer "what happens when X"
questions grounded in the graph.

**Phase 4 — Projections**
BPMN/mermaid/markdown export from graph queries. This is presentation, do
it last.

**Phase 5 — Multi-source ingestion + review UI**
Broaden connectors, add the human-in-the-loop review/correction interface.

## Open questions to resolve before/during Phase 0

- Graph store choice: Neo4j (mature, Cypher, heavier ops) vs. Kùzu or an
  embedded/SQLite-based graph (lighter, easier self-hosting story for the
  target SMB customer) vs. just modeling it in Postgres with a graph
  extension. Bias toward the lightest thing that supports multi-hop
  traversal well, given the target customer can't run a Neo4j cluster.
- Sync direction between graph and markdown vault: is markdown always
  regenerated from the graph (safer, but loses "just edit the file" appeal),
  or can humans edit markdown directly and have it re-parsed back into the
  graph (more natural, harder to keep consistent)? Recommend: graph is
  canonical, markdown is regenerated, but diffs are surfaced clearly so
  edits aren't silently lost.
- Evaluation: how do we measure extraction/resolution quality against the
  Phase 0 gold standard? Needs a lightweight eval harness early, not bolted
  on later.
- Licensing/positioning: standalone product vs. a feature that becomes an
  onboarding/consulting wedge (see prior discussion — plausible the durable
  business is "helps a company graduate to a point where classical process
  mining even works," not a forever-platform).

## Working agreement for Claude Code sessions

- Default to small, runnable increments — favor a working CLI script over a
  half-built UI.
- Every extraction/resolution change should be checked against the Phase 0
  gold-standard graph before moving on.
- Keep provenance wiring in from the start of Phase 1 — don't bolt it on
  later, it changes the schema.
- Ask before introducing a new node/edge type not listed above — keep the
  schema deliberately small until real data forces an extension.

---

# Engineering process (how code lands in this repo)

Ariadne is built on an agentic TDD workflow for Python 3.12+. All development
follows a strict red/green TDD cycle enforced by specialized subagents. Testing
with pytest, linting with ruff, TUI (kanban board) with textual. The project
brief above says *what* to build; this section governs *how* changes are made.

## TDD workflow

Every code change follows this process:

1. **Write a failing test first** — delegate to the `tdd` subagent for feature
   work. It claims the task (`status: in-progress`, `owner: tdd`), writes a
   failing test, implements minimal code, runs pytest + ruff, then hands off
   (`status: review`, `owner: reviewer`).
2. **Delegate to the `reviewer` subagent** for code review. It is read-only and
   runs on a lighter model tier in its own cleared context. It does NOT modify
   files or task status — it returns a verdict.
3. **Act on the reviewer's verdict** — orchestrator responsibility, and easy to
   forget:
   - The reviewer's final line is `VERDICT: APPROVE` or `VERDICT: REQUEST_CHANGES`.
   - On `APPROVE`: set the task's `status` to `done` and clear `owner`.
   - On `REQUEST_CHANGES`: re-delegate to the `tdd` subagent with the findings;
     the cycle repeats.

Never write implementation code before a failing test exists. The `reviewer`
cannot write files, so the orchestrator MUST perform the `review → done`
transition — do not assume the reviewer did it.

## Task management

Tasks live in `.tasks/` as markdown files with YAML frontmatter.

- **Naming**: `NNNN-short-description.md` (e.g., `0001-add-login.md`)
- **Template**: See `.tasks/_template.md` for the required frontmatter schema
- **Statuses**: `backlog` → `todo` → `in-progress` → `review` → `done`

Task status transitions:
- `tdd` sets `in-progress` (and `owner: tdd`) when starting work
- `tdd` sets `review` (and `owner: reviewer`) when implementation is complete
- The orchestrator sets `done` (and clears `owner`) when the reviewer returns
  `VERDICT: APPROVE` — the read-only reviewer cannot set it itself

## Verification commands

```bash
uv run pytest                          # Run all tests
uv run ruff check .                    # Lint check
uv run ruff format --check .           # Formatting check (fails on drift)
uv run ruff format .                   # Format code
python scripts/kanban.py --simple      # View task board (plain text)
python scripts/kanban.py               # View task board (TUI)
```

All three checks must pass before a task moves to `review`:

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check .
```

Formatter conventions are pinned in `[tool.ruff.format]` in `pyproject.toml`
(double quotes, spaces, LF, line length 88) so style stays identical across
subagent-authored files.

## Conventions

- **YAGNI**: No unnecessary abstractions. Build what's needed now.
- **Functions over classes**: Unless a class is clearly warranted.
- **Flat over nested**: Keep module structure simple.
- **No dead code**: Delete unused code, don't comment it out.
- **Tests next to code**: Tests in `tests/` mirroring `scripts/` structure.
