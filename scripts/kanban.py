"""Kanban board for .tasks/ directory — parse, render, and display."""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import yaml

STATUSES = ["backlog", "todo", "in-progress", "review", "done"]
COLUMN_LABELS = {s: s.upper() for s in STATUSES}
PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
DEFAULT_TASKS_DIR = Path(".tasks")
OWNER_STATUSES = {"in-progress", "review"}


def parse_task(path: Path) -> dict:
    """Parse a single task markdown file, extracting frontmatter and title."""
    text = path.read_text()

    # Extract YAML frontmatter
    fm_match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    frontmatter = yaml.safe_load(fm_match.group(1)) if fm_match else {}
    frontmatter = frontmatter or {}

    # Extract title from first # heading
    title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else path.stem

    return {
        "file": path.name,
        "title": title,
        "status": frontmatter.get("status", "backlog"),
        "priority": frontmatter.get("priority", "medium"),
        "owner": frontmatter.get("owner", "") or "",
        "mtime": path.stat().st_mtime,
    }


def parse_all_tasks(tasks_dir: Path = DEFAULT_TASKS_DIR) -> list[dict]:
    """Parse all task files in the directory, skipping _template.md."""
    if not tasks_dir.exists():
        return []
    tasks = []
    for path in sorted(tasks_dir.glob("*.md")):
        if path.name.startswith("_"):
            continue
        tasks.append(parse_task(path))
    return tasks


def relative_time(mtime: float, now: float) -> str:
    """Render an elapsed span as '12s ago' / '3m ago' / '1h ago'."""
    elapsed = int(now - mtime)
    if elapsed < 60:
        return f"{elapsed}s ago"
    if elapsed < 3600:
        return f"{elapsed // 60}m ago"
    return f"{elapsed // 3600}h ago"


def format_card(task: dict, now: float) -> str:
    """Return a task card's display text, with an owner line for active tasks."""
    base = f"[{task['priority']}] {task['title']}"
    if task["status"] in OWNER_STATUSES and task["owner"]:
        return f"{base}\n🤖 {task['owner']} · {relative_time(task['mtime'], now)}"
    return base


def diff_boards(old_tasks: list[dict], new_tasks: list[dict]) -> dict:
    """Report which task files were added, removed, or changed between boards."""
    old_by_file = {t["file"]: t for t in old_tasks}
    new_by_file = {t["file"]: t for t in new_tasks}

    added = set(new_by_file) - set(old_by_file)
    removed = set(old_by_file) - set(new_by_file)
    changed = set()
    for file in set(old_by_file) & set(new_by_file):
        old, new = old_by_file[file], new_by_file[file]
        if old["status"] != new["status"] or old != new:
            changed.add(file)

    return {"added": added, "removed": removed, "changed": changed}


def group_by_status(tasks: list[dict]) -> tuple[dict[str, list[dict]], list[dict]]:
    """Group tasks into known-status columns, returning also any unknown-status tasks."""
    columns: dict[str, list[dict]] = {s: [] for s in STATUSES}
    unknown = []
    for task in tasks:
        if task["status"] in columns:
            columns[task["status"]].append(task)
        else:
            unknown.append(task)
    for status in columns:
        columns[status].sort(key=lambda t: PRIORITY_ORDER.get(t["priority"], 2))
    return columns, unknown


def _warn_unknown(unknown: list[dict]) -> None:
    """Print a one-line stderr warning naming files with unknown statuses."""
    if not unknown:
        return
    details = ", ".join(f"{t['file']} (status={t['status']!r})" for t in unknown)
    print(f"warning: ignoring tasks with unknown status: {details}", file=sys.stderr)


def render_simple(tasks: list[dict]) -> str:
    """Render tasks as a plain-text columnar board."""
    columns, unknown = group_by_status(tasks)
    _warn_unknown(unknown)

    # Determine column width
    col_width = 30
    lines = []

    # Header
    header = "  ".join(label.center(col_width) for label in COLUMN_LABELS.values())
    lines.append(header)
    lines.append("  ".join("─" * col_width for _ in STATUSES))

    # Find max rows needed
    max_rows = max((len(columns[s]) for s in STATUSES), default=0)

    for row in range(max_rows):
        parts = []
        for status in STATUSES:
            col = columns[status]
            if row < len(col):
                task = col[row]
                entry = f"[{task['priority']}] {task['title']}"
                if len(entry) > col_width:
                    entry = entry[: col_width - 1] + "…"
                parts.append(entry.ljust(col_width))
            else:
                parts.append(" " * col_width)
        lines.append("  ".join(parts))

    return "\n".join(lines)


def _card_id(file: str) -> str:
    """Derive a valid Textual widget id from a task filename."""
    stem = Path(file).stem
    sanitised = re.sub(r"[^A-Za-z0-9_-]", "-", stem)
    return f"task-{sanitised}"


def main():
    """Entry point — run TUI or simple output."""
    tasks_dir = DEFAULT_TASKS_DIR

    if "--simple" in sys.argv:
        tasks = parse_all_tasks(tasks_dir)
        print(render_simple(tasks))
        return

    # TUI mode
    try:
        from textual.app import App, ComposeResult
        from textual.containers import Horizontal, Vertical
        from textual.widgets import Footer, Header, Static
    except ImportError:
        print("textual not installed. Use --simple for plain-text output.")
        sys.exit(1)

    class KanbanApp(App):
        CSS = """
        .column {
            width: 1fr;
            border: solid green;
            height: 100%;
            overflow-y: auto;
        }
        .column-title {
            text-align: center;
            text-style: bold;
            background: $accent;
            color: $text;
            padding: 0 1;
        }
        .task-card {
            margin: 0 1;
            padding: 0 1;
            border: round $secondary;
        }
        .task-card.moved {
            background: $success;
        }
        .priority-critical { color: red; }
        .priority-high { color: $warning; }
        .priority-medium { color: $text; }
        .priority-low { color: $text-muted; }
        """

        TITLE = "Kanban Board"
        BINDINGS = [("q", "quit", "Quit")]

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.tasks = parse_all_tasks(tasks_dir)

        def _make_card(self, task: dict) -> Static:
            css_class = f"task-card priority-{task['priority']}"
            card = Static(format_card(task, time.time()), classes=css_class)
            card.id = _card_id(task["file"])
            return card

        def compose(self) -> ComposeResult:
            yield Header()
            columns, unknown = group_by_status(self.tasks)
            _warn_unknown(unknown)

            with Horizontal():
                for status in STATUSES:
                    with Vertical(classes="column", id=f"col-{status}"):
                        yield Static(COLUMN_LABELS[status], classes="column-title")
                        for task in columns[status]:
                            yield self._make_card(task)
            yield Footer()

        def on_mount(self) -> None:
            self.set_interval(1.0, self.refresh_board)

        def refresh_board(self) -> None:
            new_tasks = parse_all_tasks(tasks_dir)
            diff = diff_boards(self.tasks, new_tasks)
            if not (diff["added"] or diff["removed"] or diff["changed"]):
                return

            old_by_file = {t["file"]: t for t in self.tasks}
            new_by_file = {t["file"]: t for t in new_tasks}
            _, unknown = group_by_status(new_tasks)
            _warn_unknown(unknown)

            for file in diff["removed"]:
                self._remove_card(file)

            for file in diff["added"]:
                self._mount_card(new_by_file[file])

            for file in diff["changed"]:
                old, new = old_by_file[file], new_by_file[file]
                if old["status"] != new["status"]:
                    self._remove_card(file)
                    self._mount_card(new, moved=True)
                else:
                    self._update_card(new)

            self.tasks = new_tasks

        def _remove_card(self, file: str) -> None:
            try:
                self.query_one(f"#{_card_id(file)}").remove()
            except Exception:
                pass

        def _mount_card(self, task: dict, moved: bool = False) -> None:
            if task["status"] not in STATUSES:
                return
            try:
                column = self.query_one(f"#col-{task['status']}")
            except Exception:
                return
            card = self._make_card(task)
            column.mount(card)
            if moved:
                card.add_class("moved")
                self.set_timer(1.5, lambda: card.remove_class("moved"))

        def _update_card(self, task: dict) -> None:
            try:
                card = self.query_one(f"#{_card_id(task['file'])}", Static)
            except Exception:
                return
            card.update(format_card(task, time.time()))

    KanbanApp().run()


if __name__ == "__main__":
    main()
