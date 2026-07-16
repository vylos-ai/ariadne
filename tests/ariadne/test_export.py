"""Tests for the mermaid flowchart export (``ariadne.export.to_mermaid``)."""

from pathlib import Path

from ariadne.export import to_mermaid
from ariadne.graph_store import InMemoryGraphStore
from ariadne.schema import Node, NodeType

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "returned_order"
GOLD_GRAPH_PATH = FIXTURE_DIR / "gold_graph.json"


def _gold_store() -> InMemoryGraphStore:
    store = InMemoryGraphStore()
    store.load(GOLD_GRAPH_PATH)
    return store


def test_to_mermaid_starts_with_flowchart_header():
    output = to_mermaid(_gold_store())

    assert output.startswith("flowchart TD")


def test_to_mermaid_renders_decision_as_diamond():
    output = to_mermaid(_gold_store())

    assert 'decision_inspection_outcome{"Inspection outcome"}' in output


def test_to_mermaid_renders_process_step_as_rectangle():
    output = to_mermaid(_gold_store())

    assert 'step_open_rma["Open RMA"]' in output


def test_to_mermaid_renders_exception_distinctly_from_steps():
    output = to_mermaid(_gold_store())

    # Exceptions must not use the plain rectangle shape steps use.
    assert (
        'exception_manual_reship_handoff["Manual reship handoff bottleneck"]'
        not in (output)
    )
    assert "exception_manual_reship_handoff(" in output


def test_to_mermaid_groups_steps_by_owning_role_in_subgraphs():
    output = to_mermaid(_gold_store())

    assert 'subgraph role_support["Support"]' in output
    assert 'subgraph role_warehouse["Warehouse"]' in output
    assert 'subgraph role_ops_lead["Ops Lead"]' in output

    # Steps appear nested inside their role's subgraph block.
    support_start = output.index('subgraph role_support["Support"]')
    support_end = output.index("\n  end", support_start)
    support_block = output[support_start:support_end]
    assert "step_open_rma" in support_block
    assert "step_send_label" in support_block
    assert "step_notify_denied" in support_block


def test_to_mermaid_attaches_systems_and_data_objects():
    output = to_mermaid(_gold_store())

    assert "system_order_mgmt" in output
    assert "data_return_request" in output
    # attached via dashed arrows
    assert "-.->" in output


def test_to_mermaid_never_includes_evidence_nodes_or_edges():
    output = to_mermaid(_gold_store())

    assert "evidence" not in output.lower()
    assert "evidenced_by" not in output.lower()


def test_to_mermaid_is_deterministic():
    store = _gold_store()

    first = to_mermaid(store)
    second = to_mermaid(store)

    assert first == second


def test_to_mermaid_sanitizes_hostile_labels():
    store = InMemoryGraphStore()
    store.add_node(
        Node(
            id="step-hostile",
            type=NodeType.PROCESS_STEP,
            properties={"name": 'He said "stop [now]\n| really'},
        )
    )

    output = to_mermaid(store)

    # No unescaped double quote inside the label breaks the node syntax:
    # exactly two double quotes bracket the label on its declaration line.
    for line in output.splitlines():
        if "step_hostile" in line and "[" in line:
            assert line.count('"') == 2
    assert "\n|" not in output


def test_to_mermaid_sanitizes_node_ids():
    store = InMemoryGraphStore()
    store.add_node(
        Node(
            id="step/weird id!123",
            type=NodeType.PROCESS_STEP,
            properties={"name": "Weird"},
        )
    )

    output = to_mermaid(store)

    assert "step/weird id!123" not in output
    assert "step_weird_id_123" in output
