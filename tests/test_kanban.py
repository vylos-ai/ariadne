"""Tests for the kanban board parser and renderer."""

import textwrap
from pathlib import Path

from scripts.kanban import (
    diff_boards,
    format_card,
    parse_all_tasks,
    parse_task,
    relative_time,
    render_simple,
)


def _write_task(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(content))
    return p


def test_parse_task_extracts_frontmatter(tmp_path):
    _write_task(
        tmp_path,
        "0001-login.md",
        """\
        ---
        status: todo
        priority: high
        created: 2026-01-01
        updated: 2026-01-02
        ---

        # Add login page

        ## Description
        Build a login page.
        """,
    )
    task = parse_task(tmp_path / "0001-login.md")
    assert task["status"] == "todo"
    assert task["priority"] == "high"
    assert task["title"] == "Add login page"
    assert task["file"] == "0001-login.md"


def test_parse_task_defaults_on_missing_fields(tmp_path):
    _write_task(
        tmp_path,
        "0002-bare.md",
        """\
        ---
        status: backlog
        ---

        # Bare task
        """,
    )
    task = parse_task(tmp_path / "0002-bare.md")
    assert task["status"] == "backlog"
    assert task["priority"] == "medium"
    assert task["title"] == "Bare task"


def test_parse_task_no_title_uses_filename(tmp_path):
    _write_task(
        tmp_path,
        "0003-no-title.md",
        """\
        ---
        status: todo
        ---

        No heading here.
        """,
    )
    task = parse_task(tmp_path / "0003-no-title.md")
    assert task["title"] == "0003-no-title"


def test_parse_all_tasks_skips_template(tmp_path):
    _write_task(
        tmp_path,
        "_template.md",
        """\
        ---
        status: backlog
        ---

        # Template
        """,
    )
    _write_task(
        tmp_path,
        "0001-real.md",
        """\
        ---
        status: todo
        ---

        # Real task
        """,
    )
    tasks = parse_all_tasks(tmp_path)
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Real task"


def test_parse_all_tasks_empty_dir(tmp_path):
    tasks = parse_all_tasks(tmp_path)
    assert tasks == []


def test_parse_all_tasks_groups_by_status(tmp_path):
    for i, status in enumerate(["backlog", "todo", "in-progress", "review", "done"]):
        _write_task(
            tmp_path,
            f"000{i}-task.md",
            f"""\
---
status: {status}
---

# Task {i}
""",
        )
    tasks = parse_all_tasks(tmp_path)
    statuses = {t["status"] for t in tasks}
    assert statuses == {"backlog", "todo", "in-progress", "review", "done"}


def test_render_simple_output(tmp_path):
    _write_task(
        tmp_path,
        "0001-alpha.md",
        """\
        ---
        status: todo
        priority: high
        ---

        # Alpha feature
        """,
    )
    _write_task(
        tmp_path,
        "0002-beta.md",
        """\
        ---
        status: done
        priority: low
        ---

        # Beta feature
        """,
    )
    output = render_simple(parse_all_tasks(tmp_path))
    assert "TODO" in output
    assert "DONE" in output
    assert "Alpha feature" in output
    assert "Beta feature" in output
    assert "[high]" in output
    assert "[low]" in output


def test_render_simple_empty():
    output = render_simple([])
    # Should still show column headers
    assert "BACKLOG" in output
    assert "TODO" in output
    assert "DONE" in output


# --- owner + mtime ---


def test_parse_task_extracts_owner(tmp_path):
    _write_task(
        tmp_path,
        "0010-owned.md",
        """\
        ---
        status: in-progress
        owner: tdd
        ---

        # Owned task
        """,
    )
    task = parse_task(tmp_path / "0010-owned.md")
    assert task["owner"] == "tdd"


def test_parse_task_owner_defaults_empty(tmp_path):
    _write_task(
        tmp_path,
        "0011-unowned.md",
        """\
        ---
        status: todo
        ---

        # Unowned task
        """,
    )
    task = parse_task(tmp_path / "0011-unowned.md")
    assert task["owner"] == ""


def test_parse_task_includes_mtime(tmp_path):
    p = _write_task(
        tmp_path,
        "0012-mtime.md",
        """\
        ---
        status: todo
        ---

        # Mtime task
        """,
    )
    task = parse_task(p)
    assert task["mtime"] == p.stat().st_mtime


# --- relative_time ---


def test_relative_time_seconds():
    assert relative_time(1000.0, 1012.0) == "12s ago"


def test_relative_time_minutes():
    assert relative_time(1000.0, 1000.0 + 3 * 60) == "3m ago"


def test_relative_time_hours():
    assert relative_time(1000.0, 1000.0 + 2 * 3600) == "2h ago"


def test_relative_time_boundary_60s_is_minutes():
    assert relative_time(0.0, 60.0) == "1m ago"


def test_relative_time_boundary_60m_is_hours():
    assert relative_time(0.0, 3600.0) == "1h ago"


# --- format_card ---


def _task(**overrides):
    base = {
        "file": "0001-x.md",
        "title": "A task",
        "status": "todo",
        "priority": "high",
        "owner": "",
        "mtime": 1000.0,
    }
    base.update(overrides)
    return base


def test_format_card_base_line():
    card = format_card(_task(), now=1000.0)
    assert card == "[high] A task"


def test_format_card_appends_owner_for_in_progress():
    card = format_card(
        _task(status="in-progress", owner="tdd", mtime=1000.0), now=1012.0
    )
    assert card == "[high] A task\n🤖 tdd · 12s ago"


def test_format_card_appends_owner_for_review():
    card = format_card(
        _task(status="review", owner="reviewer", mtime=1000.0), now=1000.0 + 180
    )
    assert card == "[high] A task\n🤖 reviewer · 3m ago"


def test_format_card_no_owner_line_when_owner_empty():
    card = format_card(_task(status="in-progress", owner=""), now=1012.0)
    assert card == "[high] A task"


def test_format_card_no_owner_line_for_todo_with_owner():
    card = format_card(_task(status="todo", owner="tdd"), now=1012.0)
    assert card == "[high] A task"


# --- diff_boards ---


def test_diff_boards_added():
    old = [_task(file="a.md")]
    new = [_task(file="a.md"), _task(file="b.md")]
    diff = diff_boards(old, new)
    assert "b.md" in diff["added"]
    assert not diff["removed"]
    assert not diff["changed"]


def test_diff_boards_removed():
    old = [_task(file="a.md"), _task(file="b.md")]
    new = [_task(file="a.md")]
    diff = diff_boards(old, new)
    assert "b.md" in diff["removed"]
    assert not diff["added"]
    assert not diff["changed"]


def test_diff_boards_status_changed():
    old = [_task(file="a.md", status="todo")]
    new = [_task(file="a.md", status="in-progress")]
    diff = diff_boards(old, new)
    assert "a.md" in diff["changed"]


def test_diff_boards_content_changed():
    old = [_task(file="a.md", title="Old title")]
    new = [_task(file="a.md", title="New title")]
    diff = diff_boards(old, new)
    assert "a.md" in diff["changed"]


def test_diff_boards_no_change():
    old = [_task(file="a.md")]
    new = [_task(file="a.md")]
    diff = diff_boards(old, new)
    assert not diff["added"]
    assert not diff["removed"]
    assert not diff["changed"]


# --- unknown-status guard ---


def test_render_simple_warns_on_unknown_status(tmp_path, capsys):
    _write_task(
        tmp_path,
        "0020-weird.md",
        """\
        ---
        status: frozen
        priority: high
        ---

        # Weird task
        """,
    )
    output = render_simple(parse_all_tasks(tmp_path))
    captured = capsys.readouterr()
    assert "0020-weird.md" in captured.err
    assert "frozen" in captured.err
    # unknown-status task not shown in the known columns
    assert "Weird task" not in output
