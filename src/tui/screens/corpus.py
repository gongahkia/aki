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
    Button,
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


class CorpusScreen(Screen):
    """Screen for browsing the hypothetical corpus."""

    BINDINGS = [
        Binding("escape", "pop_screen", "Back", priority=True),
        Binding("q", "pop_screen", "Back", show=False, priority=True),
        Binding("left", "pop_screen", "Back", show=False),
    ]

    CSS = """
    CorpusScreen { layout: vertical; }
    #browser-row { height: 1fr; }
    #file-tree { width: 1fr; min-width: 28; max-width: 40; border-right: tall $primary; }
    #corpus-panel { width: 3fr; }
    #corpus-table { height: 2fr; }
    #detail-panel { height: 1fr; border: tall $primary; padding: 1; overflow-y: auto; }
    #path-bar { height: auto; padding: 1; background: $surface; }
    .action-row { height: auto; margin: 1; }
    #file-tree-label { padding: 0 1; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._project_root = self._find_project_root()
        self._loaded_path: str = ""

    def _find_project_root(self) -> Path:
        """Walk up from cwd to find repo root (has corpus/ dir or .git)."""
        p = Path.cwd()
        for parent in [p, *p.parents]:
            if (parent / "corpus").is_dir() or (parent / ".git").is_dir():
                return parent
        return p

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            with Horizontal(id="path-bar"):
                yield Label("Corpus: ", id="file-tree-label")
                yield Input(
                    value=str(self._project_root / DEFAULT_CORPUS),
                    id="corpus-path-input",
                )
                yield Button("Load", variant="primary", id="load-btn")
            with Horizontal(id="browser-row"):
                yield DirectoryTree(
                    str(self._project_root),
                    id="file-tree",
                )
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
                    with Horizontal(classes="action-row"):
                        yield Button("Export CSV", id="export-csv-btn")
                        yield Button("Export JSON", id="export-json-btn")
                        yield Input(
                            placeholder="Export file path",
                            id="file-path-input",
                        )
                    yield DataTable(id="corpus-table")
                    yield Static(
                        "Select a file from the tree or press Load...",
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
            detail.update(f"[yellow]Unsupported file type: {ext}[/yellow]")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        detail = self.query_one("#detail-panel", Static)
        if event.button.id == "load-btn":
            path = self.query_one("#corpus-path-input", Input).value.strip()
            if not path:
                detail.update("[red]Enter a corpus path[/red]")
                return
            self._load_file(path)
            return
        file_path = self.query_one("#file-path-input", Input).value.strip()
        if not file_path:
            detail.update("[red]Enter an export file path[/red]")
            return
        try:
            if event.button.id == "export-csv-btn":
                self._export_csv(file_path)
                detail.update(f"[green]Exported to {file_path}[/green]")
            elif event.button.id == "export-json-btn":
                self._export_json(file_path)
                detail.update(f"[green]Exported to {file_path}[/green]")
        except Exception as e:
            detail.update(f"[red]Error: {e}[/red]")

    def _load_file(self, path: str) -> None:
        """Load a corpus file (JSON, CSV, or plaintext) into the table."""
        detail = self.query_one("#detail-panel", Static)
        table = self.query_one("#corpus-table", DataTable)
        table.clear()
        try:
            p = Path(path)
            if not p.exists():
                detail.update(f"[red]File not found: {path}[/red]")
                return
            ext = p.suffix.lower()
            entries = []
            if ext == ".json":
                entries = self._parse_json(p)
            elif ext == ".csv":
                entries = self._parse_csv(p)
            elif ext == ".txt":
                entries = self._parse_txt(p)
            else:
                detail.update(f"[yellow]Unsupported: {ext}[/yellow]")
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
            count = len(entries)
            detail.update(f"[green]Loaded {count} entries from {p.name}[/green]")
        except Exception as e:
            detail.update(f"[red]Error loading {path}: {e}[/red]")

    def _parse_json(self, p: Path) -> list:
        with open(p) as f:
            data = json.load(f)
        if isinstance(data, list):
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
                for e in data
            ]
        if isinstance(data, dict) and "entries" in data:
            return self._parse_json_list(data["entries"])
        return [{"text": json.dumps(data, indent=2), "topics": "", "quality": "N/A"}]

    def _parse_json_list(self, items: list) -> list:
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
            entries = getattr(self, "_entries", [])
            if idx < len(entries):
                e = entries[idx]
                topics = e.get("topics", "")
                header = f"[bold]{topics}[/bold]\n\n" if topics else ""
                detail.update(header + e["text"])
        except Exception as e:
            detail.update(f"Error: {e}")

    def _export_csv(self, path: str) -> None:
        entries = getattr(self, "_entries", [])
        if not entries:
            raise ValueError("No corpus data to export")
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "text", "topics", "quality"])
            for i, e in enumerate(entries):
                writer.writerow([i, e["text"], e["topics"], e.get("quality", "")])

    def _export_json(self, path: str) -> None:
        entries = getattr(self, "_entries", [])
        if not entries:
            raise ValueError("No corpus data to export")
        with open(path, "w") as f:
            json.dump(entries, f, indent=2)
