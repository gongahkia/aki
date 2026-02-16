"""Corpus browsing screen with file tree navigation and import/export."""

import csv
import json
import os
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    DataTable,
    DirectoryTree,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
)

DEFAULT_CORPUS = "corpus/clean/tort/corpus.json"
CORPUS_EXTENSIONS = {".json", ".csv", ".txt"}

SCREEN_CSS = """
CorpusScreen {
    layout: vertical;
    background: #ffffff;
    color: #1a1a1a;
}
#browser-row { height: 1fr; }
#file-tree {
    width: 1fr; min-width: 28; max-width: 40;
    border-right: tall #bdc3c7;
    background: #f8f9fa;
}
#corpus-panel { width: 3fr; background: #ffffff; }
#corpus-table { height: 2fr; }
#detail-panel {
    height: 1fr; border: tall #bdc3c7;
    padding: 1; overflow-y: auto;
    background: #f8f9fa; color: #1a1a1a;
}
#path-bar { height: auto; padding: 0 1; background: #ecf0f1; color: #1a1a1a; }
#hint-bar { height: auto; padding: 0 1; background: #ecf0f1; color: #7f8c8d; }
"""


class CorpusScreen(Screen):
    """Screen for browsing the hypothetical corpus."""

    BINDINGS = [
        Binding("escape", "pop_screen", "Back", priority=True),
        Binding("q", "pop_screen", "Back", show=False, priority=True),
        Binding("left", "pop_screen", "Back", show=False),
        Binding("f5", "load_corpus", "Load", priority=True),
        Binding("f6", "export_csv", "Export CSV", priority=True),
        Binding("f7", "export_json", "Export JSON", priority=True),
    ]

    CSS = SCREEN_CSS

    def __init__(self) -> None:
        super().__init__()
        self._project_root = self._find_project_root()
        self._loaded_path: str = ""
        self._entries: list = []

    def _find_project_root(self) -> Path:
        """Walk up from cwd to find repo root (has corpus/ dir or .git)."""
        p = Path.cwd()
        for parent in [p, *p.parents]:
            if (parent / "corpus").is_dir() or (parent / ".git").is_dir():
                return parent
        return p

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(
            "↑↓: navigate tree/table  Enter: select file  "
            "Tab: switch panes  F5: load path  F6: export CSV  F7: export JSON  "
            "Esc: back",
            id="hint-bar",
        )
        with Horizontal(id="path-bar"):
            yield Label("Path: ")
            yield Input(
                value=str(self._project_root / DEFAULT_CORPUS),
                id="corpus-path-input",
            )
        with Horizontal(id="browser-row"):
            yield DirectoryTree(str(self._project_root), id="file-tree")
            with Vertical(id="corpus-panel"):
                with Horizontal():
                    yield Input(placeholder="Search corpus...", id="search-input")
                    yield Select(
                        [
                            ("All Topics", "all"),
                            ("negligence", "negligence"),
                            ("duty_of_care", "duty_of_care"),
                            ("causation", "causation"),
                            ("remoteness", "remoteness"),
                            ("battery", "battery"),
                            ("defamation", "defamation"),
                            ("private_nuisance", "private_nuisance"),
                        ],
                        prompt="Filter topic",
                        id="topic-filter",
                    )
                yield DataTable(id="corpus-table")
                yield Static(
                    "Select a file from the tree or press F5 to load path...",
                    id="detail-panel",
                )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#corpus-table", DataTable)
        table.add_columns("ID", "Topics", "Quality", "Words", "Preview")
        default = self._project_root / DEFAULT_CORPUS
        if default.exists():
            self._load_file(str(default))

    def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        """User selected a file in the tree — update path and auto-load."""
        path = str(event.path)
        self.query_one("#corpus-path-input", Input).value = path
        ext = os.path.splitext(path)[1].lower()
        if ext in CORPUS_EXTENSIONS:
            self._load_file(path)
        else:
            detail = self.query_one("#detail-panel", Static)
            detail.update(f"Unsupported file type: {ext}")

    def action_load_corpus(self) -> None:
        path = self.query_one("#corpus-path-input", Input).value.strip()
        detail = self.query_one("#detail-panel", Static)
        if not path:
            detail.update("Enter a corpus path first")
            return
        self._load_file(path)

    def action_export_csv(self) -> None:
        self._do_export("csv")

    def action_export_json(self) -> None:
        self._do_export("json")

    def _do_export(self, fmt: str) -> None:
        detail = self.query_one("#detail-panel", Static)
        if not self._entries:
            detail.update("No corpus data to export")
            return
        base = Path(self._loaded_path) if self._loaded_path else Path("export")
        path = str(base.with_suffix(f".export.{fmt}"))
        try:
            if fmt == "csv":
                self._export_csv(path)
            else:
                self._export_json(path)
            detail.update(f"Exported to {path}")
        except Exception as e:
            detail.update(f"Error: {e}")

    def _load_file(self, path: str) -> None:
        """Load a corpus file (JSON, CSV, or plaintext) into the table."""
        detail = self.query_one("#detail-panel", Static)
        table = self.query_one("#corpus-table", DataTable)
        table.clear()
        try:
            p = Path(path)
            if not p.exists():
                detail.update(f"File not found: {path}")
                return
            ext = p.suffix.lower()
            entries: list = []
            if ext == ".json":
                entries = self._parse_json(p)
            elif ext == ".csv":
                entries = self._parse_csv(p)
            elif ext == ".txt":
                entries = self._parse_txt(p)
            else:
                detail.update(f"Unsupported: {ext}")
                return
            for i, e in enumerate(entries[:200]):
                text = e["text"]
                preview = text[:80] + "..." if len(text) > 80 else text
                topics = e.get("topics", "")
                words = str(len(text.split()))
                quality = e.get("quality", "N/A")
                table.add_row(str(i), topics, str(quality), words, preview)
            self._entries = entries
            self._loaded_path = path
            detail.update(f"Loaded {len(entries)} entries from {p.name}")
        except Exception as e:
            detail.update(f"Error loading {path}: {e}")

    def _parse_json(self, p: Path) -> list:
        with open(p) as f:
            data = json.load(f)
        if isinstance(data, list):
            return self._normalize_entries(data)
        if isinstance(data, dict) and "entries" in data:
            return self._normalize_entries(data["entries"])
        return [{"text": json.dumps(data, indent=2), "topics": "", "quality": "N/A"}]

    def _normalize_entries(self, items: list) -> list:
        return [
            {
                "text": e.get("text", str(e)),
                "topics": (
                    ", ".join(e["topic"])
                    if isinstance(e.get("topic"), list)
                    else ", ".join(e.get("topics", []))
                ),
                "quality": e.get("quality_score", "N/A"),
            }
            for e in items
        ]

    def _parse_csv(self, p: Path) -> list:
        entries = []
        with open(p) as f:
            reader = csv.DictReader(f)
            for row in reader:
                text = row.get("text", row.get("content", ""))
                topics = row.get("topic_labels", row.get("topics", ""))
                quality = row.get("quality_score", row.get("quality", "N/A"))
                entries.append({"text": text, "topics": topics, "quality": quality})
        return entries

    def _parse_txt(self, p: Path) -> list:
        text = p.read_text()
        return [{"text": text, "topics": "", "quality": "N/A"}]

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        detail = self.query_one("#detail-panel", Static)
        try:
            idx = event.cursor_row
            if idx < len(self._entries):
                e = self._entries[idx]
                topics = e.get("topics", "")
                header = f"{topics}\n\n" if topics else ""
                detail.update(header + e["text"])
        except Exception as e:
            detail.update(f"Error: {e}")

    def _export_csv(self, path: str) -> None:
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "text", "topics", "quality"])
            for i, e in enumerate(self._entries):
                writer.writerow([i, e["text"], e["topics"], e.get("quality", "")])

    def _export_json(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump(self._entries, f, indent=2)
