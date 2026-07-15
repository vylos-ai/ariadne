"""Tests for the LLM extraction provider interface.

No test in this module makes a live network call: the Anthropic-backed
provider is always exercised against a mocked client.
"""

from unittest.mock import MagicMock

from ariadne.extraction import (
    MODEL,
    AnthropicExtractionProvider,
    ExtractionResult,
    FakeExtractionProvider,
)
from ariadne.schema import EDGE_TYPES, NODE_TYPES, Edge, Node


def test_model_constant_is_a_single_string():
    assert isinstance(MODEL, str)
    assert MODEL


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


def test_anthropic_provider_builds_tool_use_request_with_schema_as_hints():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(content=[])
    mock_client.messages.create.return_value.content = [
        MagicMock(type="tool_use", input={"nodes": [], "edges": []})
    ]
    provider = AnthropicExtractionProvider(client=mock_client)

    provider.extract("some source text about a returned order")

    mock_client.messages.create.assert_called_once()
    _, kwargs = mock_client.messages.create.call_args
    assert kwargs["model"] == MODEL
    assert "some source text about a returned order" in str(kwargs["messages"])
    tool_schema = kwargs["tools"][0]
    schema_str = str(tool_schema)
    # schema types are passed as hints in the tool's input schema
    assert "ProcessStep" in schema_str
    assert "triggers" in schema_str


def test_anthropic_provider_parses_tool_use_response_into_schema_objects():
    payload = {
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
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(type="tool_use", input=payload)]
    )
    provider = AnthropicExtractionProvider(client=mock_client)

    result = provider.extract("we receive the returned order")

    assert isinstance(result, ExtractionResult)
    assert [n.id for n in result.nodes] == ["ev-1", "step-1"]
    assert result.edges[0].type.value == "evidenced_by"


def test_anthropic_provider_raises_if_no_tool_use_block_returned():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(type="text", text="no tool call")]
    )
    provider = AnthropicExtractionProvider(client=mock_client)

    try:
        provider.extract("some text")
        raised = False
    except ValueError:
        raised = True

    assert raised
