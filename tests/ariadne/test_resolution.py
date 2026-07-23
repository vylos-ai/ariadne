"""Tests for entity resolution: collapsing duplicate/near-duplicate nodes.

See CLAUDE.md Phase 2: entity resolution is "where most of the engineering
effort should go." ``resolve()`` is a pure function -- it must not mutate the
input store, and given the same input it must produce byte-identical output.
"""

import pydantic_ai.models as pydantic_ai_models
import pytest
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from ariadne.graph_store import InMemoryGraphStore
from ariadne.resolution import (
    AMBIGUITY_FLOOR,
    FakeAdjudicator,
    PydanticAIAdjudicator,
    resolve,
)
from ariadne.schema import Edge, EdgeType, Node, NodeType
from ariadne.validation import validate


@pytest.fixture(autouse=True)
def _no_live_model_requests():
    previous = pydantic_ai_models.ALLOW_MODEL_REQUESTS
    pydantic_ai_models.ALLOW_MODEL_REQUESTS = False
    yield
    pydantic_ai_models.ALLOW_MODEL_REQUESTS = previous


def _step(node_id: str, name: str, evidence_ids: list[str] | None = None) -> Node:
    return Node(
        id=node_id,
        type=NodeType.PROCESS_STEP,
        properties={"name": name},
        evidence_ids=evidence_ids or [],
    )


def _evidence(node_id: str, source: str = "doc.txt") -> Node:
    return Node(id=node_id, type=NodeType.EVIDENCE, properties={"source": source})


def test_resolve_merges_nodes_with_fuzzy_matching_labels():
    store = InMemoryGraphStore()
    store.add_node(_step("z-step", "  open rma "))
    store.add_node(_step("a-step", "Open RMA"))

    resolved = resolve(store)

    process_steps = resolved.by_type(NodeType.PROCESS_STEP)
    assert len(process_steps) == 1
    assert process_steps[0].id == "a-step"


def test_resolve_does_not_merge_across_different_node_types():
    store = InMemoryGraphStore()
    store.add_node(_step("step-1", "Widget"))
    store.add_node(
        Node(id="sys-1", type=NodeType.SYSTEM, properties={"name": "Widget"})
    )

    resolved = resolve(store)

    assert len(resolved.by_type(NodeType.PROCESS_STEP)) == 1
    assert len(resolved.by_type(NodeType.SYSTEM)) == 1


def test_resolve_never_merges_evidence_nodes():
    store = InMemoryGraphStore()
    store.add_node(_evidence("ev-1", "same text"))
    store.add_node(_evidence("ev-2", "same text"))

    resolved = resolve(store)

    assert len(resolved.by_type(NodeType.EVIDENCE)) == 2


def test_resolve_unions_evidence_ids_deduped_preserving_order():
    store = InMemoryGraphStore()
    store.add_node(_step("a-step", "Open RMA", evidence_ids=["ev-1", "ev-2"]))
    store.add_node(_step("b-step", "open rma", evidence_ids=["ev-2", "ev-3"]))

    resolved = resolve(store)

    merged = resolved.get_node("a-step")
    assert merged.evidence_ids == ["ev-1", "ev-2", "ev-3"]


def test_resolve_merges_properties_first_non_empty_wins_and_records_aliases():
    store = InMemoryGraphStore()
    store.add_node(
        Node(
            id="b-step",
            type=NodeType.PROCESS_STEP,
            properties={"name": "open rma", "owner": "Alice"},
        )
    )
    store.add_node(
        Node(id="a-step", type=NodeType.PROCESS_STEP, properties={"name": "Open RMA"})
    )

    resolved = resolve(store)

    merged = resolved.get_node("a-step")
    assert merged.properties["name"] == "Open RMA"
    assert merged.properties["owner"] == "Alice"
    assert merged.properties["aliases"] == ["open rma"]


def test_resolve_rewrites_edges_to_canonical_ids_and_dedupes():
    store = InMemoryGraphStore()
    store.add_node(_step("a-step", "Open RMA"))
    store.add_node(_step("b-step", "open rma"))
    store.add_node(_step("c-step", "Inspect"))
    store.add_edge(
        Edge(
            type=EdgeType.TRIGGERS,
            source="a-step",
            target="c-step",
            evidence_ids=["ev-1"],
        )
    )
    store.add_edge(
        Edge(
            type=EdgeType.TRIGGERS,
            source="b-step",
            target="c-step",
            evidence_ids=["ev-2"],
        )
    )

    resolved = resolve(store)

    edges = resolved.by_type(EdgeType.TRIGGERS)
    assert len(edges) == 1
    edge = edges[0]
    assert edge.source == "a-step"
    assert edge.target == "c-step"
    assert edge.evidence_ids == ["ev-1", "ev-2"]


def test_resolve_does_not_mutate_input_store():
    store = InMemoryGraphStore()
    store.add_node(_step("a-step", "Open RMA"))
    store.add_node(_step("b-step", "open rma"))

    resolve(store)

    assert len(store.by_type(NodeType.PROCESS_STEP)) == 2


def test_resolve_is_deterministic(tmp_path):
    store = InMemoryGraphStore()
    store.add_node(_step("b-step", "open rma", evidence_ids=["ev-1"]))
    store.add_node(_step("a-step", "Open RMA", evidence_ids=["ev-2"]))
    store.add_node(_step("c-step", "Inspect", evidence_ids=["ev-1"]))
    store.add_edge(
        Edge(
            type=EdgeType.TRIGGERS,
            source="b-step",
            target="c-step",
            evidence_ids=["ev-1"],
        )
    )
    store.add_edge(
        Edge(
            type=EdgeType.TRIGGERS,
            source="a-step",
            target="c-step",
            evidence_ids=["ev-2"],
        )
    )

    path1 = tmp_path / "one.json"
    path2 = tmp_path / "two.json"
    resolve(store).save(path1)
    resolve(store).save(path2)

    assert path1.read_text() == path2.read_text()


def test_resolve_above_threshold_pair_never_consults_adjudicator():
    store = InMemoryGraphStore()
    store.add_node(_step("a-step", "Open RMA"))
    store.add_node(_step("b-step", "open rma"))

    class ExplodingAdjudicator:
        def same_entity(self, node_a: Node, node_b: Node) -> bool:
            raise AssertionError("adjudicator should not be consulted")

    resolved = resolve(store, adjudicator=ExplodingAdjudicator())

    assert len(resolved.by_type(NodeType.PROCESS_STEP)) == 1


def test_resolve_band_pair_merged_when_adjudicator_affirms():
    store = InMemoryGraphStore()
    store.add_node(_step("a-step", "Open RMA"))
    store.add_node(_step("b-step", "Open Return"))
    adjudicator = FakeAdjudicator(affirm={frozenset({"a-step", "b-step"})})

    resolved = resolve(store, adjudicator=adjudicator)

    assert len(resolved.by_type(NodeType.PROCESS_STEP)) == 1


def test_resolve_band_pair_kept_separate_when_adjudicator_denies():
    store = InMemoryGraphStore()
    store.add_node(_step("a-step", "Open RMA"))
    store.add_node(_step("b-step", "Open Return"))
    adjudicator = FakeAdjudicator(affirm=set())

    resolved = resolve(store, adjudicator=adjudicator)

    assert len(resolved.by_type(NodeType.PROCESS_STEP)) == 2


def test_resolve_band_pair_unmerged_when_no_adjudicator_given():
    store = InMemoryGraphStore()
    store.add_node(_step("a-step", "Open RMA"))
    store.add_node(_step("b-step", "Open Return"))

    resolved = resolve(store)

    assert len(resolved.by_type(NodeType.PROCESS_STEP)) == 2


def test_resolve_output_passes_validation():
    store = InMemoryGraphStore()
    store.add_node(_evidence("evidence-1"))
    store.add_node(_step("a-step", "Open RMA", evidence_ids=["evidence-1"]))
    store.add_node(_step("b-step", "open rma", evidence_ids=["evidence-1"]))
    store.add_node(_step("c-step", "Inspect", evidence_ids=["evidence-1"]))
    store.add_edge(
        Edge(
            type=EdgeType.TRIGGERS,
            source="a-step",
            target="c-step",
            evidence_ids=["evidence-1"],
        )
    )
    store.add_edge(
        Edge(
            type=EdgeType.TRIGGERS,
            source="b-step",
            target="c-step",
            evidence_ids=["evidence-1"],
        )
    )

    resolved = resolve(store)

    assert validate(resolved) == []


def test_pydanticai_adjudicator_true_verdict_merges_band_pair():
    store = InMemoryGraphStore()
    store.add_node(_step("a-step", "Open RMA"))
    store.add_node(_step("b-step", "Open Return"))
    adjudicator = PydanticAIAdjudicator(
        model=TestModel(custom_output_args={"same_entity": True, "reason": "same"})
    )

    resolved = resolve(store, adjudicator=adjudicator)

    assert len(resolved.by_type(NodeType.PROCESS_STEP)) == 1


def test_pydanticai_adjudicator_false_verdict_keeps_band_pair_separate():
    store = InMemoryGraphStore()
    store.add_node(_step("a-step", "Open RMA"))
    store.add_node(_step("b-step", "Open Return"))
    adjudicator = PydanticAIAdjudicator(
        model=TestModel(
            custom_output_args={"same_entity": False, "reason": "different"}
        )
    )

    resolved = resolve(store, adjudicator=adjudicator)

    assert len(resolved.by_type(NodeType.PROCESS_STEP)) == 2


def test_pydanticai_adjudicator_not_consulted_below_ambiguity_floor():
    store = InMemoryGraphStore()
    store.add_node(_step("a-step", "Open RMA"))
    store.add_node(_step("b-step", "Completely unrelated widget assembly"))
    calls: list = []

    def fn(messages, info: AgentInfo):
        calls.append(messages)
        raise AssertionError("adjudicator should not be consulted")

    adjudicator = PydanticAIAdjudicator(model=FunctionModel(fn))

    resolved = resolve(store, adjudicator=adjudicator)

    assert not calls
    assert len(resolved.by_type(NodeType.PROCESS_STEP)) == 2


def test_pydanticai_adjudicator_not_consulted_at_or_above_auto_merge_threshold():
    store = InMemoryGraphStore()
    store.add_node(_step("a-step", "Open RMA"))
    store.add_node(_step("b-step", "open rma"))

    def fn(messages, info: AgentInfo):
        raise AssertionError("adjudicator should not be consulted")

    adjudicator = PydanticAIAdjudicator(model=FunctionModel(fn))

    resolved = resolve(store, adjudicator=adjudicator)

    assert len(resolved.by_type(NodeType.PROCESS_STEP)) == 1


def test_ambiguity_floor_is_unchanged():
    assert AMBIGUITY_FLOOR == 0.55
