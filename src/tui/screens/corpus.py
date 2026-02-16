"""Corpus browsing screen."""
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Input, DataTable, Label, Select
from textual.containers import Vertical, Horizontal, ScrollableContainer
from textual.binding import Binding


class CorpusScreen(Screen):
    """Screen for browsing the hypothetical corpus."""

    BINDINGS = [Binding("escape", "pop_screen", "Back")]

    CSS = """
    CorpusScreen { layout: vertical; }
    #corpus-table { height: 2fr; }
    #detail-panel { height: 1fr; border: tall $primary; padding: 1; }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            with Horizontal():
                yield Input(placeholder="Search corpus...", id="search-input")
                yield Select(
                    [("All Topics", "all"), ("negligence", "negligence"),
                     ("duty_of_care", "duty_of_care"), ("causation", "causation")],
                    prompt="Filter topic", id="topic-filter",
                )
            yield DataTable(id="corpus-table")
            yield Static("Select a row to view details...", id="detail-panel")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#corpus-table", DataTable)
        table.add_columns("ID", "Topics", "Quality", "Words", "Preview")
        self._load_corpus()

    def _load_corpus(self):
        """Load corpus entries into table."""
        try:
            from ...services.corpus_service import corpus_service
            table = self.query_one("#corpus-table", DataTable)
            if corpus_service._corpus:
                for entry in corpus_service._corpus[:100]:
                    text = entry.text[:80] + "..." if len(entry.text) > 80 else entry.text
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
