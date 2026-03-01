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
_PRESETS = {
    "exam_drill": {
        "label": "Exam Drill",
        "complexity": "advanced",
        "parties": "3",
        "topics": "negligence, causation",
    },
    "revision_sprint": {
        "label": "Revision Sprint",
        "complexity": "intermediate",
        "parties": "2",
        "topics": "duty_of_care",
    },
    "deep_dive": {
        "label": "Deep Dive",
        "complexity": "expert",
        "parties": "5",
        "topics": "negligence, remoteness, novus_actus_interveniens",
    },
}


class GenerateFormScreen(Screen):
    """Collects generation parameters with inline validation feedback."""

    BINDINGS = [
        Binding("escape", "close", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Container(id="screen-body"):
            yield Label("Generate", id="screen-title")
            yield Select(
                options=[
                    (preset["label"], key)
                    for key, preset in _PRESETS.items()
                ],
                value="revision_sprint",
                id="preset",
            )
            yield Input(placeholder="Topics (comma-separated)", id="topics")
            yield Input(placeholder="Parties (2-5)", id="parties")
            yield Select(
                options=[(value.title(), value) for value in _VALID_COMPLEXITY],
                value="intermediate",
                id="complexity",
            )
            yield Static("", id="preset-summary")
            yield Static("", id="topics-error")
            yield Static("", id="parties-error")
            yield Static("", id="complexity-error")
            yield Static("Press Esc to close", id="screen-help")

    def action_close(self) -> None:
        self.dismiss()

    def on_mount(self) -> None:
        self._apply_preset("revision_sprint")

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
        if event.select.id == "preset":
            selected = str(event.value or "")
            self._apply_preset(selected)
        elif event.select.id == "complexity":
            self._validate_complexity()

    def _apply_preset(self, preset_key: str) -> None:
        preset = _PRESETS.get(preset_key)
        if not preset:
            return
        self.query_one("#topics", Input).value = preset["topics"]
        self.query_one("#parties", Input).value = preset["parties"]
        self.query_one("#complexity", Select).value = preset["complexity"]
        summary = self.query_one("#preset-summary", Static)
        summary.update(
            f"[dim]{preset['label']}: topics={preset['topics']} parties={preset['parties']} complexity={preset['complexity']}[/dim]"
        )
