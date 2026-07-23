# How to test Ariadne (state: tasks 0001–0022, Phases 0–3 + Phase 4 slice)

Everything below runs from the repo root. Steps 1–4 need **no API key**.
Step 5 (live extraction) is the only one that talks to a real LLM provider.

## 0. One-time setup for the live test

Copy `.env.example` to `.env` (gitignored — never commit it) and uncomment
**one** provider profile:

```bash
cp .env.example .env
# edit .env: uncomment exactly one profile, fill in your real key
set -a; source .env; set +a
```

All LLM configuration flows through `ariadne.llm.build_model()`, which reads
three environment variables — `ARIADNE_LLM_MODEL`, `ARIADNE_LLM_BASE_URL`,
`ARIADNE_LLM_API_KEY` — so switching providers for step 5 below never
requires a source change, only a different `.env`.

> Anthropic-native profile: leave `ARIADNE_LLM_BASE_URL` unset. The model
> string keeps its `anthropic:` prefix and auth comes from the standard
> `ANTHROPIC_API_KEY` variable (not `ARIADNE_LLM_API_KEY`). Any other
> provider (Ollama, OpenRouter, ...) requires `ARIADNE_LLM_BASE_URL` set and
> an **unprefixed** `ARIADNE_LLM_MODEL` — `build_model()` raises otherwise.

> Optional tracing: set `ARIADNE_TRACE=1` (or `LOGFIRE_TOKEN=...` to ship
> traces to a Logfire project) before running any `ariadne` command to see
> which prompt, model, and response went by. It's opt-in and
> failure-tolerant — unset (the default) is a silent no-op, and a broken or
> unreachable Logfire backend never blocks the run.

## 1. Automated suite

```bash
uv run pytest                # 187 tests, incl. offline Phase 1 + Phase 2 baselines
uv run ruff check .          # lint
uv run ruff format --check . # formatting (conventions pinned in pyproject.toml)
```

The Phase 2 baseline is the interesting regression gate — full
extract → resolve → eval loop, offline with recorded payloads. It asserts the
committed metrics (node F1 0.649 unresolved → 0.941 resolved):

```bash
uv run pytest tests/ariadne/test_baseline.py -v
```

## 2. Hands-on CLI against the gold graph

The Phase 0 gold standard is a complete graph of the "returned order" process:

```bash
GOLD=tests/fixtures/returned_order/gold_graph.json

uv run ariadne validate $GOLD                          # provenance → 0 violations
uv run ariadne query $GOLD find "inspect"              # fuzzy label lookup
uv run ariadne query $GOLD describe step-inspect-item  # node + evidence-grounded facts
uv run ariadne query $GOLD what-happens step-open-rma  # downstream closure
uv run ariadne query $GOLD path step-open-rma step-process-refund
uv run ariadne resolve $GOLD --output-dir /tmp/resolved
uv run ariadne eval /tmp/resolved/graph.json $GOLD     # → P/R/F1 all 1.000
```

Expected `describe` output shape (every fact carries its evidence):

```
step-inspect-item (ProcessStep)
  triggers <- step-send-label (Send shipping label)  evidence=['evidence-interview-ops-lead']
  owned_by -> role-warehouse (Warehouse)  evidence=['evidence-email-warehouse-escalation']
  ...
```

## 3. Diagram projection

```bash
uv run ariadne export $GOLD > process.mmd
```

Paste `process.mmd` into <https://mermaid.live> (or any GitHub markdown file)
→ flowchart with role swimlanes, decisions as diamonds, no evidence nodes.

## 4. MCP — let Claude query the graph (Phase 3 payoff)

```bash
claude mcp add ariadne -- uv run --project /home/demiurg/Projekte/Ariadne \
    ariadne mcp /home/demiurg/Projekte/Ariadne/tests/fixtures/returned_order/gold_graph.json
```

Then start a new Claude Code session and ask:
*"What happens when a returned order comes in? Who owns the inspection?"*
Claude should answer via the `find_nodes` / `describe` / `what_happens` tools,
citing evidence ids. Remove again with `claude mcp remove ariadne`.

## 5. Live extraction quality, provider-parameterised (needs a key from step 0)

This is the payoff of tasks 0019–0022: the extract → validate → resolve →
eval loop runs unchanged against whichever provider `.env` points at. Costs a
few real API calls per run.

```bash
set -a; source .env; set +a

uv run ariadne extract \
    tests/fixtures/returned_order/email_customer_complaint.txt \
    tests/fixtures/returned_order/email_warehouse_escalation.txt \
    tests/fixtures/returned_order/interview_ops_lead.txt \
    --output-dir /tmp/live

uv run ariadne validate /tmp/live/graph.json

# --adjudicate consults the LLM on ambiguity-band entity-resolution pairs
# (task 0021). Off by default — costs extra calls, worth trying once to see
# if it moves the resolved-graph F1.
uv run ariadne resolve /tmp/live/graph.json --output-dir /tmp/live-resolved
uv run ariadne resolve /tmp/live/graph.json --output-dir /tmp/live-resolved-adj \
    --adjudicate

uv run ariadne eval /tmp/live-resolved/graph.json \
    tests/fixtures/returned_order/gold_graph.json
uv run ariadne eval /tmp/live-resolved-adj/graph.json \
    tests/fixtures/returned_order/gold_graph.json
```

How to read the result:
- **Grounding** should be 100% — anything less is a provenance bug, not a
  quality issue.
- **Node/edge P/R/F1** vs gold is the honest extraction-quality number. The
  offline Phase 2 baseline (0.941 node F1) is plumbing verification, not a
  prediction — live numbers will likely be lower. If they're far off, the
  levers are the extraction instructions in `src/ariadne/extraction.py` and
  the `--adjudicate` flag above, not the provider.

### Comparing models

Because every provider knob (`ARIADNE_LLM_MODEL`, `ARIADNE_LLM_BASE_URL`,
`ARIADNE_LLM_API_KEY`) is an environment variable, you can run the exact same
loop above against N models and diff the eval reports — nothing in the
pipeline changes, only `.env`:

> `.env.anthropic`, `.env.ollama`, and any other per-provider file below hold
> **real credentials**. They are matched by the `.env.*` rule in
> `.gitignore` (with `!.env.example` carving out the one file that's meant to
> be committed), so they're safe to create in the working tree — `git
> status` will never offer them up. Only `.env.example` is ever tracked.

```bash
# Run 1 — Anthropic native
set -a; source .env.anthropic; set +a
uv run ariadne extract ... --output-dir /tmp/live-anthropic
uv run ariadne resolve /tmp/live-anthropic/graph.json --output-dir /tmp/live-anthropic-resolved
uv run ariadne eval /tmp/live-anthropic-resolved/graph.json \
    tests/fixtures/returned_order/gold_graph.json > /tmp/eval-anthropic.txt

# Run 2 — same loop, different .env (e.g. Ollama or OpenRouter profile)
set -a; source .env.ollama; set +a
uv run ariadne extract ... --output-dir /tmp/live-ollama
uv run ariadne resolve /tmp/live-ollama/graph.json --output-dir /tmp/live-ollama-resolved
uv run ariadne eval /tmp/live-ollama-resolved/graph.json \
    tests/fixtures/returned_order/gold_graph.json > /tmp/eval-ollama.txt

diff /tmp/eval-anthropic.txt /tmp/eval-ollama.txt
```

(Keep one `.env.<provider>` file per profile you want to compare — see
`.env.example` for the three worked profiles — and source the one you want
before each run.)

Set `ARIADNE_TRACE=1` (or `LOGFIRE_TOKEN=...`) alongside any of the runs
above to inspect the actual prompts/responses per model in Logfire.
