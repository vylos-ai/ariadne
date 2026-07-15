"""LLM-backed extraction provider: source text -> candidate nodes/edges.

The ``ExtractionProvider`` interface takes free source text (an email, a
transcript excerpt, ...) and returns *candidate* graph elements -- nodes and
edges from the schema defined in :mod:`ariadne.schema`. The schema is passed
to the LLM as a *hint* in the tool's input schema description, not enforced
as a rigid constraint, so extraction isn't forced into an ill-fitting
category (see CLAUDE.md).

Every node/edge returned by a provider is built via
``ariadne.schema.node_from_dict``/``edge_from_dict``, so extraction output is
guaranteed to validate against the 0002 schema -- including the provenance
rule that non-``evidenced_by`` edges must carry at least one evidence id.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import anthropic

from ariadne.schema import (
    EDGE_TYPES,
    NODE_TYPES,
    Edge,
    Node,
    edge_from_dict,
    node_from_dict,
)

# Single source of truth for the extraction model id. The exact model is
# deferred/configurable -- this is a reasonable current default.
MODEL = "claude-sonnet-4-5-20250929"

_TOOL_NAME = "record_process_elements"

_TOOL_SCHEMA = {
    "name": _TOOL_NAME,
    "description": (
        "Record candidate process-graph nodes and edges extracted from the "
        "source text. Node/edge types are hints, not rigid constraints -- "
        "use the closest fit rather than forcing a bad categorization."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "nodes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "type": {
                            "type": "string",
                            "description": f"Hint, one of: {sorted(NODE_TYPES)}",
                        },
                        "properties": {"type": "object"},
                        "evidence_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["id", "type"],
                },
            },
            "edges": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "description": f"Hint, one of: {sorted(EDGE_TYPES)}",
                        },
                        "source": {"type": "string"},
                        "target": {"type": "string"},
                        "evidence_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["type", "source", "target"],
                },
            },
        },
        "required": ["nodes", "edges"],
    },
}


@dataclass
class ExtractionResult:
    """Candidate nodes/edges extracted from a piece of source text."""

    nodes: list[Node]
    edges: list[Edge]


class ExtractionProvider(Protocol):
    """Anything that can extract graph candidates from source text."""

    def extract(self, text: str) -> ExtractionResult: ...


def _payload_to_result(payload: dict) -> ExtractionResult:
    """Build an ``ExtractionResult``, validating against the 0002 schema."""
    nodes = [node_from_dict(n) for n in payload.get("nodes", [])]
    edges = [edge_from_dict(e) for e in payload.get("edges", [])]
    return ExtractionResult(nodes=nodes, edges=edges)


_DEFAULT_PAYLOAD = {
    "nodes": [
        {
            "id": "ev-1",
            "type": "Evidence",
            "properties": {"text": "we receive the returned order and log it"},
        },
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


class FakeExtractionProvider:
    """Offline stand-in for tests: returns canned, schema-conforming output.

    Makes no network calls. Defaults to a small built-in example; pass
    ``payload`` (in the same shape the real provider's tool would return) to
    customize what a given test sees.
    """

    def __init__(self, payload: dict | None = None) -> None:
        self._payload = payload if payload is not None else _DEFAULT_PAYLOAD

    def extract(self, text: str) -> ExtractionResult:
        del text  # canned output does not depend on input
        return _payload_to_result(self._payload)


class AnthropicExtractionProvider:
    """Real provider: wraps the Anthropic API behind ``ExtractionProvider``.

    Uses tool-use (structured output) with the node/edge schema passed as a
    hint via the tool's input schema description. A client must be supplied
    explicitly in tests (a mock) to guarantee no live API calls are made;
    when omitted, a real ``anthropic.Anthropic()`` client is constructed.
    """

    def __init__(
        self, client: anthropic.Anthropic | None = None, model: str = MODEL
    ) -> None:
        self._client = client if client is not None else anthropic.Anthropic()
        self._model = model

    def extract(self, text: str) -> ExtractionResult:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            tools=[_TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": _TOOL_NAME},
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Extract process-graph nodes and edges from the "
                        f"following source text using the {_TOOL_NAME} "
                        f"tool.\n\n{text}"
                    ),
                }
            ],
        )
        for block in response.content:
            if getattr(block, "type", None) == "tool_use":
                return _payload_to_result(block.input)
        raise ValueError("Anthropic response did not contain a tool_use block")
