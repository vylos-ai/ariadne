---
status: done
priority: critical
owner:
created: 2026-07-15
updated: 2026-07-15
---

# Domain schema (nodes, edges, first-class provenance)

## Description

Define the node/edge domain model as lightweight dataclasses (data over classes
where possible, per conventions). Cover the 8 node types (ProcessStep, Decision,
Role, System, DataObject, Exception, Policy, Evidence) and 9 edge types (triggers,
requires, produces, owned_by, escalates_to, depends_on, contradicts, supersedes,
evidenced_by). **Provenance is first-class**: every edge and every non-trivial node
property carries Evidence references — this is the trust boundary from CLAUDE.md.
Structures must be dict-serializable (for the JSON store and markdown vault) and
temporal-ready (facts can be superseded later, not overwritten).

## Acceptance Criteria

- [ ] Node model covers all 8 node types with stable `id`, `type`, `properties`, and evidence references
- [ ] Edge model covers all 9 edge types with `type`, `source`, `target`, and evidence reference
- [ ] Constructing a non-`Evidence`-linking edge without evidence is rejected/flagged (provenance enforced in-schema)
- [ ] Nodes and edges round-trip to/from plain `dict` with no data loss
- [ ] `uv run pytest` and `uv run ruff check .` pass

## Notes

Dependencies: 0001.
Keep the schema deliberately small — do NOT add node/edge types beyond the lists
above (CLAUDE.md: ask before extending the schema).
Temporal reification (supersede-don't-overwrite) is a later task; just leave the
door open in the data model here.
