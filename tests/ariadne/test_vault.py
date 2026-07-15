import yaml

from ariadne.graph_store import InMemoryGraphStore
from ariadne.schema import Edge, EdgeType, Node, NodeType
from ariadne.vault import parse_vault_file, render_node, render_vault


def _step(node_id: str, name: str) -> Node:
    return Node(
        id=node_id,
        type=NodeType.PROCESS_STEP,
        properties={"name": name},
        evidence_ids=["evidence-1"],
    )


def _role(node_id: str, name: str) -> Node:
    return Node(id=node_id, type=NodeType.ROLE, properties={"name": name})


def _build_store() -> InMemoryGraphStore:
    store = InMemoryGraphStore()
    store.add_node(_step("step-1", "Receive return request"))
    store.add_node(_step("step-2", "Inspect item"))
    store.add_node(_role("role-1", "Warehouse Clerk"))
    store.add_edge(
        Edge(
            type=EdgeType.TRIGGERS,
            source="step-1",
            target="step-2",
            evidence_ids=["evidence-1"],
        )
    )
    store.add_edge(
        Edge(
            type=EdgeType.OWNED_BY,
            source="step-1",
            target="role-1",
            evidence_ids=["evidence-1"],
        )
    )
    return store


def test_render_node_has_valid_yaml_frontmatter():
    store = _build_store()
    node = store.get_node("step-1")
    text = render_node(node, store)

    assert text.startswith("---\n")
    frontmatter_raw = text.split("---\n", 2)[1]
    frontmatter = yaml.safe_load(frontmatter_raw)

    assert frontmatter["id"] == "step-1"
    assert frontmatter["type"] == "ProcessStep"
    assert frontmatter["properties"] == {"name": "Receive return request"}
    assert frontmatter["evidence_ids"] == ["evidence-1"]


def test_render_node_groups_related_nodes_as_wiki_links_by_edge_type():
    store = _build_store()
    node = store.get_node("step-1")
    text = render_node(node, store)

    assert "## triggers" in text
    assert "[[step-2]]" in text
    assert "## owned_by" in text
    assert "[[role-1]]" in text
    # groups are alphabetically ordered by edge type (deterministic ordering)
    assert text.index("## owned_by") < text.index("## triggers")


def test_render_node_is_deterministic():
    store = _build_store()
    node = store.get_node("step-1")
    first = render_node(node, store)
    second = render_node(node, store)
    assert first == second


def test_render_vault_is_deterministic_across_runs(tmp_path):
    store = _build_store()

    dir_a = tmp_path / "vault_a"
    dir_b = tmp_path / "vault_b"
    render_vault(store, dir_a)
    render_vault(store, dir_b)

    files_a = sorted(dir_a.glob("*.md"))
    files_b = sorted(dir_b.glob("*.md"))
    assert [f.name for f in files_a] == [f.name for f in files_b]
    for fa, fb in zip(files_a, files_b, strict=True):
        assert fa.read_bytes() == fb.read_bytes()


def test_render_vault_writes_one_file_per_node(tmp_path):
    store = _build_store()
    vault_dir = tmp_path / "vault"
    render_vault(store, vault_dir)

    written = {f.stem for f in vault_dir.glob("*.md")}
    assert written == {"step-1", "step-2", "role-1"}


def test_parse_vault_file_recovers_frontmatter_and_links(tmp_path):
    store = _build_store()
    vault_dir = tmp_path / "vault"
    render_vault(store, vault_dir)

    parsed = parse_vault_file(vault_dir / "step-1.md")

    assert parsed["id"] == "step-1"
    assert parsed["type"] == "ProcessStep"
    assert parsed["properties"] == {"name": "Receive return request"}
    assert parsed["evidence_ids"] == ["evidence-1"]
    assert parsed["links"]["triggers"] == ["step-2"]
    assert parsed["links"]["owned_by"] == ["role-1"]
