# How to test Ariadne (state: tasks 0001–0017, Phases 0–3 + Phase 4 slice)

Everything below runs from the repo root. Steps 1–4 need **no API key**.
Step 5 (live extraction) is the only one that talks to the Anthropic API.

## 0. One-time setup for the live test

Put your real key into `.env` (the file exists with a placeholder, and is
gitignored — never commit it):

```bash
# edit .env, replace REPLACE_ME_WITH_YOUR_KEY, then load it:
set -a; source .env; set +a
```

> Note: nothing auto-loads `.env` — the `anthropic` SDK reads the
> `ANTHROPIC_API_KEY` environment variable, so you must source it (or export
> the variable some other way) in the shell you run step 5 from.

## 1. Automated suite

```bash
uv run pytest                # 170 tests, incl. offline Phase 1 + Phase 2 baselines
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

## 5. Live extraction quality (needs the API key from step 0)

This is the one thing not yet measured: real LLM extraction on the messy
sources, scored against gold. Costs a few API calls.

```bash
set -a; source .env; set +a

uv run ariadne extract \
    tests/fixtures/returned_order/email_customer_complaint.txt \
    tests/fixtures/returned_order/email_warehouse_escalation.txt \
    tests/fixtures/returned_order/interview_ops_lead.txt \
    --output-dir /tmp/live

uv run ariadne validate /tmp/live/graph.json
uv run ariadne resolve /tmp/live/graph.json --output-dir /tmp/live-resolved
uv run ariadne eval /tmp/live-resolved/graph.json \
    tests/fixtures/returned_order/gold_graph.json
```

How to read the result:
- **Grounding** should be 100% — anything less is a provenance bug, not a
  quality issue.
- **Node/edge P/R/F1** vs gold is the honest extraction-quality number. The
  offline Phase 2 baseline (0.941 node F1) is plumbing verification, not a
  prediction — live numbers will likely be lower. If they're far off, the next
  lever is the extraction prompt in `src/ariadne/extraction.py`, and the
  ambiguity-band adjudicator (`resolve(store, adjudicator=AnthropicAdjudicator())`)
  which the v1 CLI deliberately doesn't wire in yet.
