"""History screen with pagination and topic/provider filtering."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import DataTable, Input, Label, Select, Static


class HistoryScreen(Screen):
    """SQLite-backed generation history browser."""

    BINDINGS = [
        Binding("left", "prev_page", "Prev"),
        Binding("right", "next_page", "Next"),
        Binding("escape", "close", "Close"),
    ]

    _all_records: List[Dict[str, Any]] = []
    _filtered_records: List[Dict[str, Any]] = []
    _page_size = 20
    _page = 0

    def compose(self) -> ComposeResult:
        with Container(id="screen-body"):
            yield Label("History", id="screen-title")
            with Horizontal():
                yield Input(placeholder="Filter topic", id="topic-filter")
                yield Select(
                    options=[("All providers", "all")],
                    value="all",
                    id="provider-filter",
                )
            yield DataTable(id="history-table")
            yield Static("Page 1/1", id="history-page")
            yield Static("Use left/right to paginate.", id="screen-help")

    def on_mount(self) -> None:
        table = self.query_one("#history-table", DataTable)
        table.add_columns("ID", "Timestamp", "Topic", "Provider", "Score")
        asyncio.create_task(self._load_records())

    async def _load_records(self) -> None:
        page = self.query_one("#history-page", Static)
        page.update("Loading history...")
        try:
            from ...services.database_service import database_service

            records = await database_service.get_history_records(limit=500)
            if isinstance(records, list):
                self._all_records = records
            else:
                self._all_records = []
            self._filtered_records = list(self._all_records)
            self._rebuild_provider_filter()
            self._render_page()
        except Exception as exc:
            page.update(f"Failed to load history: {exc}")

    def action_close(self) -> None:
        self.dismiss()

    def action_prev_page(self) -> None:
        if self._page > 0:
            self._page -= 1
            self._render_page()

    def action_next_page(self) -> None:
        max_page = max(0, (len(self._filtered_records) - 1) // self._page_size)
        if self._page < max_page:
            self._page += 1
            self._render_page()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "topic-filter":
            self._apply_filters()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "provider-filter":
            self._apply_filters()

    def _rebuild_provider_filter(self) -> None:
        provider_filter = self.query_one("#provider-filter", Select)
        providers = sorted(
            {
                str((record.get("request") or {}).get("provider", "")).strip().lower()
                for record in self._all_records
            }
        )
        providers = [provider for provider in providers if provider]
        provider_filter.set_options(
            [("All providers", "all")]
            + [(provider, provider) for provider in providers]
        )
        provider_filter.value = "all"

    def _apply_filters(self) -> None:
        topic_query = self.query_one("#topic-filter", Input).value.strip().lower()
        provider_value = str(
            self.query_one("#provider-filter", Select).value or "all"
        ).strip()

        filtered: List[Dict[str, Any]] = []
        for record in self._all_records:
            request = record.get("request") or {}
            topics = [str(t).lower() for t in request.get("topics", [])]
            provider = str(request.get("provider", "")).strip().lower()

            topic_match = True
            if topic_query:
                topic_match = any(topic_query in topic for topic in topics)

            provider_match = provider_value == "all" or provider == provider_value

            if topic_match and provider_match:
                filtered.append(record)

        self._filtered_records = filtered
        self._page = 0
        self._render_page()

    def _render_page(self) -> None:
        table = self.query_one("#history-table", DataTable)
        page_label = self.query_one("#history-page", Static)

        table.clear()
        start = self._page * self._page_size
        end = start + self._page_size
        page_records = self._filtered_records[start:end]

        for record in page_records:
            request = record.get("request") or {}
            response = record.get("response") or {}
            topics = request.get("topics", [])
            topic_label = ", ".join(topics[:2]) if isinstance(topics, list) else "-"
            provider = str(request.get("provider", "-") or "-")
            score = response.get("validation_results", {}).get("quality_score", "-")
            table.add_row(
                str(record.get("id", "-")),
                str(record.get("timestamp", "-")),
                topic_label,
                provider,
                str(score),
            )

        total_pages = max(1, (len(self._filtered_records) + self._page_size - 1) // self._page_size)
        page_label.update(
            f"Page {self._page + 1}/{total_pages} | records={len(self._filtered_records)}"
        )
