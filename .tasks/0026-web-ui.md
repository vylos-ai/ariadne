---
status: done
priority: high
owner:
created: 2026-07-23
updated: 2026-07-23
---

# Browser UI — process diagram + evidence drill-down

## Description

The browser half of `ariadne serve` (API is task 0025). Its job is the trust
loop: make it fast to answer "is this fact actually supported by the source?"
for any node or edge in the graph.

Primary user is internal — inspecting extraction output while quality is still
unproven — so optimise for finding errors fast, not for looking impressive.

## Acceptance Criteria

- [x] A single-page UI served at `/`, self-contained: no CDN, no external
      fonts, no network calls beyond this server. It must work offline and on a
      laptop with no internet.
- [x] Three regions: a left sidebar listing nodes grouped by type with counts;
      the process diagram; and a detail panel for the selected node.
- [x] The diagram renders the mermaid from `/api/mermaid` (same projection the
      CLI emits — the graph stays the single source of truth). Vendor the
      mermaid library locally rather than loading it from a CDN.
- [x] Clicking a node — in the sidebar or the diagram — opens its detail panel:
      type, properties, and every incident fact as
      `<edge type> <direction> <neighbor label>`.
- [x] **The trust loop, the point of this task:** every fact shows its evidence,
      and the evidence expands inline to the verbatim source text from
      `/api/evidence/{id}`. Getting from any claim to the words it came from
      must take one click and never leave the page.
- [x] `Exception` nodes are visually distinct. They carry the tribal knowledge
      the tool exists to surface ("reship handoff gap", "unclear owner of denial
      email") and are the first thing worth looking at in a new graph.
- [x] Nodes with no evidence are visibly flagged. `validate` should prevent
      these, but the UI must show it rather than hide it — a silently
      ungrounded fact is the one failure mode that makes the graph untrustworthy.
- [x] Readable at a laptop window size; wide content (diagram, long source
      excerpts) scrolls in its own container rather than the page scrolling
      sideways.
- [x] Works against `.json`, `.db` and `.sqlite` graphs (it only talks to the
      API, so this should be free — verify, don't assume).
- [x] `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` pass

## Notes

No build step, no framework, no bundler — plain HTML/CSS/JS served as a static
asset. A toolchain here would be a maintenance cost with no benefit at this
size, and would violate the repo's YAGNI rule.

Keep the CSS neutral and legible; this is an inspection tool, not a brand
surface. Support light and dark.

## Review outcome

Approved. Verified interactively with Playwright rather than by reading: trust
loop, diagram clicks, zero off-origin requests, light+dark, no body overflow.
Two defects found by driving the real UI that 229 passing tests and a clean
code review both missed:

1. `/api/evidence/{id}` hardcoded `text`/`source` and dropped every other
   property, so the trust loop dead-ended on the gold graph (which stores its
   content under `summary`). Now returns the full properties dict.
2. Mermaid renders labels as HTML in a foreignObject and re-parses them
   downstream of app.js's escapeHtml, so `<img src=x onerror=...>` in an
   extracted node name had its handler stripped but the tag preserved -- the
   browser then fetched the src. No script execution, but an attacker-
   controlled src is an outbound beacon and breaks the offline guarantee.
   Fixed with `htmlLabels: false` (SVG text labels), removing the vector class
   rather than blacklisting tags. Confirmed with a hostile-graph browser test;
   regression-pinned in test_web.py.

Known rough edge: at 100% zoom the initial scroll position can land in sparse
swimlane whitespace. Defaulting to Fit is a one-line change if that first
impression matters more than immediate legibility.
