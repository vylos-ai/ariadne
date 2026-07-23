"""Tests for the LLM extraction provider interface.

No test in this module makes a live network call: the Pydantic AI-backed
provider is always exercised against ``TestModel``/``FunctionModel`` test
doubles, with ``pydantic_ai.models.ALLOW_MODEL_REQUESTS`` forced off so an
accidental live call fails loudly instead of hitting the network.
"""

import pydantic_ai.models as pydantic_ai_models
import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from ariadne.extraction import (
    ExtractionPayload,
    ExtractionResult,
    FakeExtractionProvider,
    PydanticAIExtractionProvider,
)
from ariadne.schema import EDGE_TYPES, NODE_TYPES, Edge, Node


@pytest.fixture(autouse=True)
def _no_live_model_requests():
    previous = pydantic_ai_models.ALLOW_MODEL_REQUESTS
    pydantic_ai_models.ALLOW_MODEL_REQUESTS = False
    yield
    pydantic_ai_models.ALLOW_MODEL_REQUESTS = previous


def test_fake_provider_returns_schema_conforming_output_no_network():
    provider = FakeExtractionProvider()

    result = provider.extract("we receive the returned order and log it")

    assert isinstance(result, ExtractionResult)
    assert result.nodes, "expected at least one candidate node"
    assert result.edges, "expected at least one candidate edge"
    for node in result.nodes:
        assert isinstance(node, Node)
        assert node.type.value in NODE_TYPES
    for edge in result.edges:
        assert isinstance(edge, Edge)
        assert edge.type.value in EDGE_TYPES
        # provenance is first-class: every edge must be evidence-backed,
        # enforced by ariadne.schema.Edge itself.


def test_fake_provider_accepts_custom_canned_payload():
    payload = {
        "nodes": [
            {"id": "ev-1", "type": "Evidence", "properties": {"text": "quote"}},
            {
                "id": "role-1",
                "type": "Role",
                "properties": {"name": "AP Clerk"},
                "evidence_ids": ["ev-1"],
            },
        ],
        "edges": [
            {
                "type": "evidenced_by",
                "source": "role-1",
                "target": "ev-1",
                "evidence_ids": [],
            }
        ],
    }
    provider = FakeExtractionProvider(payload)

    result = provider.extract("anything")

    assert [n.id for n in result.nodes] == ["ev-1", "role-1"]
    assert result.edges[0].source == "role-1"


def test_extraction_payload_type_hints_are_plain_strings_not_enums():
    # Node/edge types must remain hints (per CLAUDE.md), not rigid
    # Literal/Enum constraints -- otherwise extraction gets forced into a
    # bad categorization instead of using the closest fit.
    node_fields = ExtractionPayload.model_fields["nodes"].annotation
    node_type_field = node_fields.__args__[0].model_fields["type"]
    edge_fields = ExtractionPayload.model_fields["edges"].annotation
    edge_type_field = edge_fields.__args__[0].model_fields["type"]

    assert node_type_field.annotation is str
    assert edge_type_field.annotation is str
    assert "ProcessStep" in node_type_field.description
    assert "triggers" in edge_type_field.description


def test_pydanticai_provider_parses_agent_output_into_schema_objects():
    payload_args = {
        "nodes": [
            {"id": "ev-1", "type": "Evidence", "properties": {"text": "quote"}},
            {
                "id": "step-1",
                "type": "ProcessStep",
                "properties": {"name": "Receive returned order"},
                "evidence_ids": ["ev-1"],
            },
        ],
        "edges": [
            {
                "type": "evidenced_by",
                "source": "step-1",
                "target": "ev-1",
                "evidence_ids": [],
            }
        ],
    }
    provider = PydanticAIExtractionProvider(
        model=TestModel(custom_output_args=payload_args)
    )

    result = provider.extract("we receive the returned order")

    assert isinstance(result, ExtractionResult)
    assert [n.id for n in result.nodes] == ["ev-1", "step-1"]
    assert result.edges[0].type.value == "evidenced_by"


def test_pydanticai_provider_rejects_ungrounded_edge_via_schema_post_init():
    # The provenance trust boundary must survive the port: an edge with no
    # evidence and a non-evidenced_by type is rejected by schema.Edge, not
    # silently accepted.
    payload_args = {
        "nodes": [{"id": "step-1", "type": "ProcessStep", "properties": {}}],
        "edges": [
            {
                "type": "triggers",
                "source": "step-1",
                "target": "step-1",
                "evidence_ids": [],
            }
        ],
    }
    provider = PydanticAIExtractionProvider(
        model=TestModel(custom_output_args=payload_args)
    )

    with pytest.raises(ValueError, match="evidence"):
        provider.extract("some source text")


def test_pydanticai_provider_sends_source_text_and_real_instructions_to_model():
    # End-to-end check that the production agent (built by the real
    # constructor path, not a hand-assembled test agent) both forwards the
    # source text unmodified and actually configures the model with the
    # slug-id and evidence-per-edge rules -- not a parallel agent that could
    # silently diverge from what the CLI builds.
    captured: dict = {}

    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        captured["messages"] = messages
        captured["info"] = info
        return ModelResponse(parts=[TextPart('{"nodes": [], "edges": []}')])

    provider = PydanticAIExtractionProvider(model=FunctionModel(fn))

    provider.extract("some source text about a returned order")

    prompt = captured["messages"][0].parts[0].content
    assert prompt == "some source text about a returned order"

    instructions = (captured["info"].instructions or "").lower()
    assert instructions, "expected non-empty instructions to reach the model"
    assert "slug" in instructions
    assert "evidence" in instructions
