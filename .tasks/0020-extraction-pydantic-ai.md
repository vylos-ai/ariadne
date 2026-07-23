---
status: todo
priority: high
owner:
created: 2026-07-23
updated: 2026-07-23
---

# Port extraction to Pydantic AI

## Description

Replace `AnthropicExtractionProvider` (hand-written Anthropic tool-use schema,
direct SDK client) with a provider-agnostic `PydanticAIExtractionProvider` built
on `llm.build_model()` from task 0019. Structured output moves from a
hand-maintained JSON tool schema to pydantic models.

The provenance trust boundary must not move: extraction output still lands in
the `schema.py` dataclasses, so `Edge.__post_init__` stays the last gate that
rejects an ungrounded edge.

## Acceptance Criteria

- [ ] Pydantic models mirror the current tool schema: `ExtractedNode`
      (`id`, `type`, `properties`, `evidence_ids`), `ExtractedEdge`
      (`type`, `source`, `target`, `evidence_ids`), `ExtractionPayload`
      (`nodes`, `edges`)
- [ ] Node/edge type lists appear as **hints** in field descriptions, not as
      rigid enums (CLAUDE.md: hints, not constraints — avoid false categorization)
- [ ] `PydanticAIExtractionProvider` implements the existing `ExtractionProvider`
      protocol, builds `Agent(build_model(), output_type=ExtractionPayload,
      instructions=...)`, and converts via the existing `_payload_to_result`
- [ ] `AnthropicExtractionProvider` and the `anthropic` import are removed
- [ ] Instructions carry the previously-implicit rules: stable slug ids, and
      every non-`evidenced_by` edge must reference at least one evidence id
- [ ] `FakeExtractionProvider` unchanged; the whole offline suite still runs
      through it
- [ ] `cli.py::_default_provider()` returns the new provider
- [ ] Tests use pydantic-ai test doubles (`TestModel` / `FunctionModel` with
      `agent.override(model=...)`), plus a fixture setting
      `pydantic_ai.models.ALLOW_MODEL_REQUESTS = False` so an accidental live
      call fails loudly
- [ ] Phase 1 + Phase 2 baseline metrics unchanged (node F1 0.649 → 0.941,
      edge F1 1.000, grounding 100%) — any movement means graph semantics changed
- [ ] `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` pass

## Notes

Verify the exact test-double import paths against the installed pydantic-ai
version before writing the test — do not trust these names blindly:
`pydantic_ai.models.test.TestModel`, `pydantic_ai.models.function.FunctionModel`,
`pydantic_ai.models.ALLOW_MODEL_REQUESTS`.

`_payload_to_result` and the dataclass conversion stay — do not let pydantic
models leak past the provider boundary into the graph store.
