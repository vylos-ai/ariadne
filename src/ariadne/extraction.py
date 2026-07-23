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

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel

from ariadne.llm import build_model
from ariadne.schema import (
    EDGE_TYPES,
    NODE_TYPES,
    Edge,
    Node,
    edge_from_dict,
    node_from_dict,
)


class ExtractedNode(BaseModel):
    """A candidate node, as returned by the extraction agent."""

    id: str = Field(
        description=(
            "Stable, lowercase slug id, e.g. 'receive-returned-order'. Reuse "
            "the same id for the same real-world entity across the text."
        )
    )
    type: str = Field(description=f"Hint, one of: {sorted(NODE_TYPES)}")
    properties: dict = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)


class ExtractedEdge(BaseModel):
    """A candidate edge, as returned by the extraction agent."""

    type: str = Field(description=f"Hint, one of: {sorted(EDGE_TYPES)}")
    source: str
    target: str
    evidence_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Every edge except 'evidenced_by' must reference at least one "
            "evidence id -- an edge with no evidence will be rejected."
        ),
    )


class ExtractionPayload(BaseModel):
    """Candidate process-graph nodes/edges extracted from source text."""

    nodes: list[ExtractedNode] = Field(default_factory=list)
    edges: list[ExtractedEdge] = Field(default_factory=list)


_INSTRUCTIONS = (
    "Extract candidate process-graph nodes and edges from the source text "
    "you are given. Node/edge types are hints, not rigid constraints -- use "
    "the closest fit rather than forcing a bad categorization.\n\n"
    "Node ids must be stable, lowercase slugs: reuse the same id every time "
    "the same real-world entity (step, role, system, document, ...) is "
    "referenced, so nodes can be linked across edges and across documents.\n\n"
    "Provenance is first-class: every edge except 'evidenced_by' must "
    "reference at least one evidence id pointing at the Evidence node it "
    "was inferred from. Do not emit an edge you cannot ground in the text."
)


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


class PydanticAIExtractionProvider:
    """Real provider: wraps a Pydantic AI ``Agent`` behind ``ExtractionProvider``.

    Provider-agnostic -- the underlying model is whatever ``build_model()``
    (see ``ariadne.llm``) resolves from configuration, so swapping LLM
    vendors is an environment-variable change, not a code change. Structured
    output is enforced by pydantic (``ExtractionPayload``); a Pydantic AI
    test double (``TestModel``/``FunctionModel``) can be passed directly as
    ``model=`` in tests to guarantee no live API calls are made -- they are
    themselves model objects, so no separate constructor seam is needed.
    """

    def __init__(self, model: str | OpenAIChatModel | None = None) -> None:
        self.agent = Agent(
            model if model is not None else build_model(),
            output_type=ExtractionPayload,
            instructions=_INSTRUCTIONS,
        )

    def extract(self, text: str) -> ExtractionResult:
        result = self.agent.run_sync(text)
        return _payload_to_result(result.output.model_dump())
