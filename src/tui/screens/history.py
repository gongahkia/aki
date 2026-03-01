"""History screen with pagination and topic/provider filtering."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, Dict, List

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Button, DataTable, Input, Label, Select, Static

from ...services.error_mapper import map_exception

class HistoryScreen(Screen):
    """SQLite-backed generation history browser."""

    BINDINGS = [
        Binding("left", "prev_page", "Prev"),
        Binding("right", "next_page", "Next"),
        Binding("enter", "show_detail", "Detail"),
        Binding("escape", "close", "Close"),
    ]

    _all_records: List[Dict[str, Any]] = []
    _filtered_records: List[Dict[str, Any]] = []
    _page_records: List[Dict[str, Any]] = []
    _page_size = 20
    _page = 0

    def __init__(self, *, history_service=None, workflow_service=None) -> None:
        super().__init__()
        if history_service is None:
            from ...services.database_service import database_service

            history_service = database_service
        if workflow_service is None:
            from ...services.workflow_facade import workflow_facade

            workflow_service = workflow_facade
        self._history_service = history_service
        self._workflow_service = workflow_service

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
            with Horizontal():
                yield Button("Regenerate", id="history-action-regenerate")
                yield Button("Export", id="history-action-export")
                yield Button("Report", id="history-action-report")
            yield Static("Action: idle", id="history-action-status")
            with Horizontal():
                yield Static("Hypothetical", id="detail-hypothetical")
                yield Static("Analysis", id="detail-analysis")
                yield Static("Metadata", id="detail-metadata")
            yield Static("Use left/right to paginate.", id="screen-help")

    def on_mount(self) -> None:
        table = self.query_one("#history-table", DataTable)
        table.add_columns("ID", "Timestamp", "Topic", "Provider", "Score")
        asyncio.create_task(self._load_records())

    async def _load_records(self) -> None:
        page = self.query_one("#history-page", Static)
        page.update("Loading history...")
        try:
            records = await self._history_service.get_history_records(limit=500)
            if isinstance(records, list):
                self._all_records = records
            else:
                self._all_records = []
            self._filtered_records = list(self._all_records)
            self._rebuild_provider_filter()
            self._render_page()
        except Exception as exc:
            mapped = map_exception(exc, default_status=500)
            page.update(f"Failed to load history: {mapped.message}")

    def action_close(self) -> None:
        self.dismiss()

    def action_show_detail(self) -> None:
        self._update_detail_from_cursor()

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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        action = event.button.id or ""
        if action == "history-action-regenerate":
            asyncio.create_task(self._regenerate_selected())
        elif action == "history-action-export":
            asyncio.create_task(self._export_selected())
        elif action == "history-action-report":
            asyncio.create_task(self._report_selected())

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
        self._page_records = page_records

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
        self._update_detail_from_cursor()

    def _update_detail_from_cursor(self) -> None:
        table = self.query_one("#history-table", DataTable)
        if not self._page_records:
            self.query_one("#detail-hypothetical", Static).update("Hypothetical: -")
            self.query_one("#detail-analysis", Static).update("Analysis: -")
            self.query_one("#detail-metadata", Static).update("Metadata: -")
            return

        row_index = max(0, min(table.cursor_row, len(self._page_records) - 1))
        record = self._page_records[row_index]
        response = record.get("response") or {}
        hypothetical = str(response.get("hypothetical", ""))[:400] or "-"
        analysis = str(response.get("analysis", ""))[:400] or "-"
        metadata = json.dumps(response.get("metadata", {}), indent=2)[:400] or "-"

        self.query_one("#detail-hypothetical", Static).update(hypothetical)
        self.query_one("#detail-analysis", Static).update(analysis)
        self.query_one("#detail-metadata", Static).update(metadata)

    def _selected_record(self) -> Dict[str, Any] | None:
        if not self._page_records:
            return None
        table = self.query_one("#history-table", DataTable)
        row_index = max(0, min(table.cursor_row, len(self._page_records) - 1))
        return self._page_records[row_index]

    async def _regenerate_selected(self) -> None:
        status = self.query_one("#history-action-status", Static)
        record = self._selected_record()
        if not record:
            status.update("Action: no record selected")
            return
        generation_id = record.get("id")
        if not generation_id:
            status.update("Action: selected row has no generation id")
            return
        try:
            correlation_id = f"tui-regenerate-{uuid.uuid4()}"
            await self._workflow_service.regenerate_generation(
                generation_id=int(generation_id),
                correlation_id=correlation_id,
            )
            status.update(
                f"Action: regenerated generation_id={generation_id} correlation_id={correlation_id}"
            )
        except Exception as exc:
            mapped = map_exception(exc, default_status=500)
            status.update(f"Action: regenerate failed ({mapped.message})")

    async def _export_selected(self) -> None:
        status = self.query_one("#history-action-status", Static)
        record = self._selected_record()
        if not record:
            status.update("Action: no record selected")
            return
        try:
            response = record.get("response") or {}
            hypothetical = str(response.get("hypothetical", "")).strip()
            generation_id = record.get("id", "unknown")
            correlation_id = f"tui-export-{uuid.uuid4()}"
            if not hypothetical:
                status.update("Action: export skipped (empty hypothetical)")
                return
            out_path = f"data/export_{generation_id}_{correlation_id}.txt"
            with open(out_path, "w", encoding="utf-8") as handle:
                handle.write(hypothetical)
            status.update(f"Action: exported {out_path}")
        except Exception as exc:
            mapped = map_exception(exc, default_status=500)
            status.update(f"Action: export failed ({mapped.message})")

    async def _report_selected(self) -> None:
        status = self.query_one("#history-action-status", Static)
        record = self._selected_record()
        if not record:
            status.update("Action: no record selected")
            return
        generation_id = record.get("id")
        if not generation_id:
            status.update("Action: selected row has no generation id")
            return
        try:
            correlation_id = f"tui-report-{uuid.uuid4()}"
            await self._workflow_service.save_generation_report(
                generation_id=int(generation_id),
                issue_types=["manual_review"],
                comment=(
                    "Reported from Textual history screen. "
                    f"correlation_id={correlation_id}"
                ),
            )
            status.update(
                f"Action: report saved for generation_id={generation_id} correlation_id={correlation_id}"
            )
        except Exception as exc:
            mapped = map_exception(exc, default_status=500)
            status.update(f"Action: report failed ({mapped.message})")
