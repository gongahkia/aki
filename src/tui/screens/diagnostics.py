"""Diagnostics screen for local TUI latency metrics."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import DataTable, Label, Static

from ..services import latency_metrics


class DiagnosticsScreen(Screen):
    """Display p50/p95 latency metrics for instrumented TUI actions."""

    BINDINGS = [
        Binding("r", "refresh", "Refresh"),
        Binding("escape", "close", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Container(id="screen-body"):
            yield Label("Diagnostics", id="screen-title")
            yield DataTable(id="latency-table")
            yield Static("Press r to refresh", id="screen-help")

    def on_mount(self) -> None:
        table = self.query_one("#latency-table", DataTable)
        table.add_columns("Action", "Count", "p50 (ms)", "p95 (ms)")
        self._render_metrics()

    def action_refresh(self) -> None:
        self._render_metrics()

    def action_close(self) -> None:
        self.dismiss()

    def _render_metrics(self) -> None:
        table = self.query_one("#latency-table", DataTable)
        table.clear()
        for action, metric in sorted(latency_metrics.summary().items()):
            table.add_row(
                action,
                str(int(metric.get("count", 0))),
                str(metric.get("p50_ms", 0.0)),
                str(metric.get("p95_ms", 0.0)),
            )
