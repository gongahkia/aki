"""First-run setup wizard screen for Textual runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Label, Static


@dataclass(frozen=True)
class WizardStep:
    title: str
    description: str


class SetupWizardScreen(Screen):
    """Guided first-run setup with forward/back navigation."""

    BINDINGS = [
        Binding("n", "next_step", "Next"),
        Binding("b", "prev_step", "Back"),
        Binding("escape", "close", "Close"),
    ]

    _steps: Tuple[WizardStep, ...] = (
        WizardStep("Environment", "Create .env and configure provider keys."),
        WizardStep("Corpus", "Verify local corpus path and topic extraction."),
        WizardStep("Providers", "Check local-first provider health and model access."),
        WizardStep("Ready", "Confirm defaults and enter main workflow."),
    )
    current_step = reactive(0)

    def compose(self) -> ComposeResult:
        with Container(id="screen-body"):
            yield Label("Setup Wizard", id="screen-title")
            yield Static(id="wizard-progress")
            yield Static(id="wizard-content")
            yield Static("Keys: n next, b back, Esc close", id="screen-help")

    def on_mount(self) -> None:
        self._render_step()

    def _render_step(self) -> None:
        total = len(self._steps)
        index = max(0, min(self.current_step, total - 1))
        step = self._steps[index]
        progress = self.query_one("#wizard-progress", Static)
        content = self.query_one("#wizard-content", Static)
        progress.update(f"Step {index + 1}/{total}: {step.title}")
        content.update(step.description)

    def action_next_step(self) -> None:
        if self.current_step < len(self._steps) - 1:
            self.current_step += 1

    def action_prev_step(self) -> None:
        if self.current_step > 0:
            self.current_step -= 1

    def action_close(self) -> None:
        self.dismiss()

    def watch_current_step(self) -> None:
        self._render_step()
