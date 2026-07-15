import pytest

from ariadne.schema import (
    EDGE_TYPES,
    NODE_TYPES,
    Edge,
    EdgeType,
    Node,
    NodeType,
    edge_from_dict,
    edge_to_dict,
    node_from_dict,
    node_to_dict,
)


def test_node_types_cover_all_eight():
    assert NODE_TYPES == {
        "ProcessStep",
        "Decision",
        "Role",
        "System",
        "DataObject",
        "Exception",
        "Policy",
        "Evidence",
    }
    assert {t.value for t in NodeType} == NODE_TYPES


def test_edge_types_cover_all_nine():
    assert EDGE_TYPES == {
        "triggers",
        "requires",
        "produces",
        "owned_by",
        "escalates_to",
        "depends_on",
        "contradicts",
        "supersedes",
        "evidenced_by",
    }
    assert {t.value for t in EdgeType} == EDGE_TYPES


def test_node_has_stable_id_type_properties_and_evidence():
    node = Node(
        id="step-1",
        type=NodeType.PROCESS_STEP,
        properties={"name": "Receive return request"},
        evidence_ids=["evidence-1"],
    )
    assert node.id == "step-1"
    assert node.type == NodeType.PROCESS_STEP
    assert node.properties == {"name": "Receive return request"}
    assert node.evidence_ids == ["evidence-1"]


def test_node_evidence_ids_default_empty():
    node = Node(id="ev-1", type=NodeType.EVIDENCE, properties={})
    assert node.evidence_ids == []


def test_edge_has_type_source_target_and_evidence():
    edge = Edge(
        type=EdgeType.TRIGGERS,
        source="step-1",
        target="step-2",
        evidence_ids=["evidence-1"],
    )
    assert edge.type == EdgeType.TRIGGERS
    assert edge.source == "step-1"
    assert edge.target == "step-2"
    assert edge.evidence_ids == ["evidence-1"]


def test_edge_without_evidence_is_rejected():
    with pytest.raises(ValueError, match="evidence"):
        Edge(type=EdgeType.REQUIRES, source="step-1", target="step-2")


def test_edge_without_evidence_ids_list_but_empty_is_rejected():
    with pytest.raises(ValueError, match="evidence"):
        Edge(
            type=EdgeType.DEPENDS_ON,
            source="step-1",
            target="step-2",
            evidence_ids=[],
        )


def test_evidenced_by_edge_does_not_require_evidence():
    # An evidenced_by edge IS the provenance link itself, so it is exempt.
    edge = Edge(type=EdgeType.EVIDENCED_BY, source="step-1", target="evidence-1")
    assert edge.evidence_ids == []


def test_node_round_trips_through_dict_with_no_data_loss():
    node = Node(
        id="role-1",
        type=NodeType.ROLE,
        properties={"name": "Warehouse Clerk", "department": "Logistics"},
        evidence_ids=["evidence-1", "evidence-2"],
    )
    d = node_to_dict(node)
    assert d == {
        "id": "role-1",
        "type": "Role",
        "properties": {"name": "Warehouse Clerk", "department": "Logistics"},
        "evidence_ids": ["evidence-1", "evidence-2"],
    }
    restored = node_from_dict(d)
    assert restored == node


def test_edge_round_trips_through_dict_with_no_data_loss():
    edge = Edge(
        type=EdgeType.OWNED_BY,
        source="step-1",
        target="role-1",
        evidence_ids=["evidence-1"],
    )
    d = edge_to_dict(edge)
    assert d == {
        "type": "owned_by",
        "source": "step-1",
        "target": "role-1",
        "evidence_ids": ["evidence-1"],
    }
    restored = edge_from_dict(d)
    assert restored == edge


def test_all_node_types_constructible():
    for node_type in NodeType:
        node = Node(id=f"n-{node_type.value}", type=node_type, properties={})
        assert node.type == node_type


def test_all_edge_types_constructible_with_evidence():
    for edge_type in EdgeType:
        kwargs = {"type": edge_type, "source": "a", "target": "b"}
        if edge_type != EdgeType.EVIDENCED_BY:
            kwargs["evidence_ids"] = ["evidence-1"]
        edge = Edge(**kwargs)
        assert edge.type == edge_type
