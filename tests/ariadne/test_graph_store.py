import pytest

from ariadne.graph_store import GraphStore, InMemoryGraphStore
from ariadne.schema import Edge, EdgeType, Node, NodeType
from ariadne.sqlite_store import SqliteGraphStore


def _step(node_id: str, name: str) -> Node:
    return Node(id=node_id, type=NodeType.PROCESS_STEP, properties={"name": name})


def _role(node_id: str, name: str) -> Node:
    return Node(id=node_id, type=NodeType.ROLE, properties={"name": name})


@pytest.fixture(params=["memory", "sqlite"])
def store(request, tmp_path):
    if request.param == "memory":
        return InMemoryGraphStore()
    return SqliteGraphStore(tmp_path / "graph.db")


def test_graph_store_is_a_graph_store(store):
    assert isinstance(store, GraphStore)


def test_add_node_and_get_node(store):
    node = _step("step-1", "Receive return request")
    store.add_node(node)
    assert store.get_node("step-1") == node


def test_get_node_missing_returns_none(store):
    assert store.get_node("nope") is None


def test_add_node_upserts_existing_id(store):
    store.add_node(_step("step-1", "Receive return request"))
    updated = _step("step-1", "Receive return request v2")
    store.add_node(updated)
    assert store.get_node("step-1") == updated
    assert len(store.by_type(NodeType.PROCESS_STEP)) == 1


def test_add_edge_requires_both_nodes_to_exist(store):
    store.add_node(_step("step-1", "Receive return request"))
    edge = Edge(
        type=EdgeType.TRIGGERS,
        source="step-1",
        target="step-2",
        evidence_ids=["evidence-1"],
    )
    with pytest.raises(ValueError, match="step-2"):
        store.add_edge(edge)


def test_add_edge_rejects_missing_source_node(store):
    store.add_node(_step("step-2", "Inspect item"))
    edge = Edge(
        type=EdgeType.TRIGGERS,
        source="step-1",
        target="step-2",
        evidence_ids=["evidence-1"],
    )
    with pytest.raises(ValueError, match="step-1"):
        store.add_edge(edge)


def test_add_edge_succeeds_when_both_nodes_exist(store):
    store.add_node(_step("step-1", "Receive return request"))
    store.add_node(_step("step-2", "Inspect item"))
    edge = Edge(
        type=EdgeType.TRIGGERS,
        source="step-1",
        target="step-2",
        evidence_ids=["evidence-1"],
    )
    store.add_edge(edge)
    assert edge in store.neighbors("step-1")


def test_neighbors_returns_edges_in_both_directions(store):
    store.add_node(_step("step-1", "Receive return request"))
    store.add_node(_role("role-1", "Warehouse Clerk"))
    edge = Edge(
        type=EdgeType.OWNED_BY,
        source="step-1",
        target="role-1",
        evidence_ids=["evidence-1"],
    )
    store.add_edge(edge)
    assert edge in store.neighbors("step-1")
    assert edge in store.neighbors("role-1")


def test_neighbors_filterable_by_edge_type(store):
    store.add_node(_step("step-1", "Receive return request"))
    store.add_node(_step("step-2", "Inspect item"))
    store.add_node(_role("role-1", "Warehouse Clerk"))
    triggers_edge = Edge(
        type=EdgeType.TRIGGERS,
        source="step-1",
        target="step-2",
        evidence_ids=["evidence-1"],
    )
    owned_by_edge = Edge(
        type=EdgeType.OWNED_BY,
        source="step-1",
        target="role-1",
        evidence_ids=["evidence-1"],
    )
    store.add_edge(triggers_edge)
    store.add_edge(owned_by_edge)

    triggers_only = store.neighbors("step-1", edge_type=EdgeType.TRIGGERS)
    assert triggers_only == [triggers_edge]

    owned_by_only = store.neighbors("step-1", edge_type=EdgeType.OWNED_BY)
    assert owned_by_only == [owned_by_edge]


def test_neighbors_for_unknown_node_returns_empty_list(store):
    assert store.neighbors("nope") == []


def test_neighbors_does_not_unique_on_source_target_pair(store):
    """Two differently-typed edges between the same node pair must both survive."""
    store.add_node(_step("step-1", "Receive return request"))
    store.add_node(_step("step-2", "Inspect item"))
    triggers_edge = Edge(
        type=EdgeType.TRIGGERS,
        source="step-1",
        target="step-2",
        evidence_ids=["evidence-1"],
    )
    depends_on_edge = Edge(
        type=EdgeType.DEPENDS_ON,
        source="step-1",
        target="step-2",
        evidence_ids=["evidence-1"],
    )
    store.add_edge(triggers_edge)
    store.add_edge(depends_on_edge)

    neighbors = store.neighbors("step-1")
    assert len(neighbors) == 2
    assert triggers_edge in neighbors
    assert depends_on_edge in neighbors


def test_by_type_filters_nodes(store):
    step = _step("step-1", "Receive return request")
    role = _role("role-1", "Warehouse Clerk")
    store.add_node(step)
    store.add_node(role)
    assert store.by_type(NodeType.PROCESS_STEP) == [step]
    assert store.by_type(NodeType.ROLE) == [role]
    assert store.by_type(NodeType.SYSTEM) == []


def test_by_type_filters_edges(store):
    store.add_node(_step("step-1", "Receive return request"))
    store.add_node(_step("step-2", "Inspect item"))
    edge = Edge(
        type=EdgeType.TRIGGERS,
        source="step-1",
        target="step-2",
        evidence_ids=["evidence-1"],
    )
    store.add_edge(edge)
    assert store.by_type(EdgeType.TRIGGERS) == [edge]
    assert store.by_type(EdgeType.REQUIRES) == []


def test_save_and_load_round_trips_with_no_data_loss(store, tmp_path):
    step = _step("step-1", "Receive return request")
    role = _role("role-1", "Warehouse Clerk")
    store.add_node(step)
    store.add_node(role)
    edge = Edge(
        type=EdgeType.OWNED_BY,
        source="step-1",
        target="role-1",
        evidence_ids=["evidence-1"],
    )
    store.add_edge(edge)

    path = tmp_path / "graph.json"
    store.save(path)

    restored = InMemoryGraphStore()
    restored.load(path)

    assert restored.get_node("step-1") == step
    assert restored.get_node("role-1") == role
    assert restored.neighbors("step-1") == [edge]
    assert restored.by_type(NodeType.PROCESS_STEP) == [step]
    assert restored.by_type(EdgeType.OWNED_BY) == [edge]


def test_sqlite_store_persists_after_close_and_reopen(tmp_path):
    """SQLite-only: durability across process/connection restarts, which the
    in-memory backend cannot express since it has no persistent handle."""
    db_path = tmp_path / "graph.db"
    store = SqliteGraphStore(db_path)
    step = _step("step-1", "Receive return request")
    role = _role("role-1", "Warehouse Clerk")
    store.add_node(step)
    store.add_node(role)
    edge = Edge(
        type=EdgeType.OWNED_BY,
        source="step-1",
        target="role-1",
        evidence_ids=["evidence-1"],
    )
    store.add_edge(edge)
    store.close()

    reopened = SqliteGraphStore(db_path)
    assert reopened.get_node("step-1") == step
    assert reopened.get_node("role-1") == role
    assert reopened.neighbors("step-1") == [edge]
    reopened.close()
