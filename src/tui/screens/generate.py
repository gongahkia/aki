"""Dedicated generation form screen with inline validation."""

from __future__ import annotations

from typing import List

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Input, Label, Select, Static

_VALID_COMPLEXITY = ["beginner", "basic", "intermediate", "advanced", "expert"]


class GenerateFormScreen(Screen):
    """Collects generation parameters with inline validation feedback."""

    BINDINGS = [
        Binding("escape", "close", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Container(id="screen-body"):
            yield Label("Generate", id="screen-title")
            yield Input(placeholder="Topics (comma-separated)", id="topics")
            yield Input(placeholder="Parties (2-5)", id="parties")
            yield Select(
                options=[(value.title(), value) for value in _VALID_COMPLEXITY],
                value="intermediate",
                id="complexity",
            )
            yield Static("", id="topics-error")
            yield Static("", id="parties-error")
            yield Static("", id="complexity-error")
            yield Static("Press Esc to close", id="screen-help")

    def action_close(self) -> None:
        self.dismiss()

    def on_key(self, event: Key) -> None:
        if event.key == "enter":
            self._validate_all()

    def _topics(self) -> List[str]:
        raw = self.query_one("#topics", Input).value
        return [topic.strip() for topic in raw.split(",") if topic.strip()]

    def _validate_topics(self) -> bool:
        topics = self._topics()
        error = self.query_one("#topics-error", Static)
        if not topics:
            error.update("[red]At least one topic is required.[/red]")
            return False
        if len(topics) > 10:
            error.update("[red]Maximum 10 topics allowed.[/red]")
            return False
        error.update("")
        return True

    def _validate_parties(self) -> bool:
        raw = self.query_one("#parties", Input).value.strip()
        error = self.query_one("#parties-error", Static)
        if not raw:
            error.update("[red]Party count is required.[/red]")
            return False
        try:
            parties = int(raw)
        except ValueError:
            error.update("[red]Party count must be an integer.[/red]")
            return False
        if parties < 2 or parties > 5:
            error.update("[red]Party count must be between 2 and 5.[/red]")
            return False
        error.update("")
        return True

    def _validate_complexity(self) -> bool:
        selected = self.query_one("#complexity", Select).value
        error = self.query_one("#complexity-error", Static)
        if selected not in _VALID_COMPLEXITY:
            error.update("[red]Complexity must be a supported level.[/red]")
            return False
        error.update("")
        return True

    def _validate_all(self) -> bool:
        topics_valid = self._validate_topics()
        parties_valid = self._validate_parties()
        complexity_valid = self._validate_complexity()
        return topics_valid and parties_valid and complexity_valid

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "topics":
            self._validate_topics()
        elif event.input.id == "parties":
            self._validate_parties()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "complexity":
            self._validate_complexity()
