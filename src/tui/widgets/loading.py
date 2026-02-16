"""Reusable loading, progress, and status widgets."""

from textual.widgets import Static, ProgressBar
from textual.app import ComposeResult
from textual.containers import Vertical


class LoadingSpinner(Static):
    """Simple loading spinner widget."""

    DEFAULT_CSS = "LoadingSpinner { height: auto; }"

    def __init__(self, message: str = "Loading..."):
        super().__init__(f"⏳ {message}")
        self._message = message

    def update_message(self, message: str):
        self._message = message
        self.update(f"⏳ {message}")

    def set_done(self, message: str = "Done"):
        self.update(f"✅ {message}")

    def set_error(self, message: str = "Error"):
        self.update(f"❌ {message}")


class ProgressBarWithETA(Vertical):
    """Progress bar with percentage and ETA display."""

    DEFAULT_CSS = "ProgressBarWithETA { height: auto; }"

    def compose(self) -> ComposeResult:
        yield ProgressBar(total=100, show_eta=True, id="progress")
        yield Static("0%", id="progress-label")

    def set_progress(self, value: float, message: str = ""):
        bar = self.query_one("#progress", ProgressBar)
        label = self.query_one("#progress-label", Static)
        bar.update(progress=int(value * 100))
        pct = f"{value * 100:.0f}%"
        label.update(f"{pct} {message}" if message else pct)


class StatusChecklist(Vertical):
    """Status checklist with green check / red x / yellow spinner per item."""

    DEFAULT_CSS = "StatusChecklist { height: auto; padding: 1; }"

    def __init__(self):
        super().__init__()
        self._items = {}

    def add_item(self, key: str, label: str, status: str = "pending"):
        """Add or update a status item. status: pending, running, success, error."""
        self._items[key] = {"label": label, "status": status}
        self._refresh_display()

    def set_status(self, key: str, status: str):
        if key in self._items:
            self._items[key]["status"] = status
            self._refresh_display()

    def _refresh_display(self):
        icons = {"pending": "⬜", "running": "🔄", "success": "✅", "error": "❌"}
        lines = []
        for item in self._items.values():
            icon = icons.get(item["status"], "⬜")
            lines.append(f"{icon} {item['label']}")
        self.remove_children()
        self.mount(Static("\n".join(lines)))
