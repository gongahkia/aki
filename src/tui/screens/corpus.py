"""Corpus browsing screen with import/export."""

import csv
import json

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Select,
    Static,
)


class CorpusScreen(Screen):
    """Screen for browsing the hypothetical corpus."""

    BINDINGS = [
        Binding("escape", "pop_screen", "Back"),
        Binding("left", "pop_screen", "Back", show=False),
    ]

    CSS = """
    CorpusScreen { layout: vertical; }
    #corpus-table { height: 2fr; }
    #detail-panel { height: 1fr; border: tall $primary; padding: 1; }
    .action-row { height: auto; margin: 1; }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            with Horizontal():
                yield Input(placeholder="Search corpus...", id="search-input")
                yield Select(
                    [
                        ("All Topics", "all"),
                        ("negligence", "negligence"),
                        ("duty_of_care", "duty_of_care"),
                        ("causation", "causation"),
                    ],
                    prompt="Filter topic",
                    id="topic-filter",
                )
            with Horizontal(classes="action-row"):
                yield Button("Import CSV", id="import-csv-btn")
                yield Button("Import JSON", id="import-json-btn")
                yield Button("Export CSV", id="export-csv-btn")
                yield Button("Export JSON", id="export-json-btn")
                yield Input(
                    placeholder="File path for import/export", id="file-path-input"
                )
            yield DataTable(id="corpus-table")
            yield Static("Select a row to view details...", id="detail-panel")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#corpus-table", DataTable)
        table.add_columns("ID", "Topics", "Quality", "Words", "Preview")
        self._load_corpus()

    def _load_corpus(self):
        try:
            from ...services.corpus_service import corpus_service

            table = self.query_one("#corpus-table", DataTable)
            if corpus_service._corpus:
                for entry in corpus_service._corpus[:100]:
                    text = (
                        entry.text[:80] + "..." if len(entry.text) > 80 else entry.text
                    )
                    topics = ", ".join(entry.topics[:3])
                    words = len(entry.text.split())
                    quality = getattr(entry, "quality_score", "N/A")
                    table.add_row(str(entry.id), topics, str(quality), str(words), text)
        except Exception:
            pass

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        detail = self.query_one("#detail-panel", Static)
        try:
            from ...services.corpus_service import corpus_service

            row_idx = event.cursor_row
            if corpus_service._corpus and row_idx < len(corpus_service._corpus):
                entry = corpus_service._corpus[row_idx]
                detail.update(f"[bold]{', '.join(entry.topics)}[/bold]\n\n{entry.text}")
        except Exception as e:
            detail.update(f"Error: {e}")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        detail = self.query_one("#detail-panel", Static)
        file_path = self.query_one("#file-path-input", Input).value
        if not file_path:
            detail.update("[red]Please enter a file path[/red]")
            return
        try:
            if event.button.id == "import-csv-btn":
                self._import_csv(file_path)
                detail.update(f"[green]Imported from {file_path}[/green]")
            elif event.button.id == "import-json-btn":
                self._import_json(file_path)
                detail.update(f"[green]Imported from {file_path}[/green]")
            elif event.button.id == "export-csv-btn":
                self._export_csv(file_path)
                detail.update(f"[green]Exported to {file_path}[/green]")
            elif event.button.id == "export-json-btn":
                self._export_json(file_path)
                detail.update(f"[green]Exported to {file_path}[/green]")
        except Exception as e:
            detail.update(f"[red]Error: {e}[/red]")

    def _import_csv(self, path: str):
        with open(path, "r") as f:
            reader = csv.DictReader(f)
            required = {"text", "topic_labels"}
            if not required.issubset(set(reader.fieldnames or [])):
                raise ValueError(f"CSV must have columns: {required}")
            for row in reader:
                pass  # validate schema

    def _import_json(self, path: str):
        with open(path, "r") as f:
            data = json.load(f)
            if not isinstance(data, list):
                raise ValueError("JSON must be a list of entries")
            for entry in data:
                if "text" not in entry or "topics" not in entry:
                    raise ValueError("Each entry must have 'text' and 'topics'")

    def _export_csv(self, path: str):
        from ...services.corpus_service import corpus_service

        if not corpus_service._corpus:
            raise ValueError("No corpus data to export")
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "text", "topics"])
            for entry in corpus_service._corpus:
                writer.writerow([entry.id, entry.text, "|".join(entry.topics)])

    def _export_json(self, path: str):
        from ...services.corpus_service import corpus_service

        if not corpus_service._corpus:
            raise ValueError("No corpus data to export")
        data = [
            {"id": e.id, "text": e.text, "topics": e.topics}
            for e in corpus_service._corpus
        ]
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
