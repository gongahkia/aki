"""Guided demo flow screen optimized for screenshot capture."""

from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Button, Label, Static


class DemoFlowScreen(Screen):
    """Run a deterministic showcase flow suitable for README screenshots."""

    BINDINGS = [
        Binding("n", "next_step", "Next"),
        Binding("escape", "close", "Close"),
    ]

    _steps = [
        "Step 1: Validate local-first provider readiness.",
        "Step 2: Preview deterministic exam-drill configuration.",
        "Step 3: Stream seeded hypothetical output.",
        "Step 4: Show validation panel and export-ready status.",
    ]

    def compose(self) -> ComposeResult:
        with Container(id="screen-body"):
            yield Label("Demo Flow", id="screen-title")
            yield Static("Step 1/4", id="demo-progress")
            yield Static(self._steps[0], id="demo-step")
            yield Static(
                "Preset=Exam Drill | seed=424242 | provider=ollama | model=llama3",
                id="demo-config",
            )
            yield Button("Run Next Step", id="demo-next")
            yield Static("Demo status: idle", id="demo-status")

    def on_mount(self) -> None:
        self._step_index = 0

    def action_close(self) -> None:
        self.dismiss()

    def action_next_step(self) -> None:
        asyncio.create_task(self._advance_step())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "demo-next":
            asyncio.create_task(self._advance_step())

    async def _advance_step(self) -> None:
        status = self.query_one("#demo-status", Static)
        progress = self.query_one("#demo-progress", Static)
        step_text = self.query_one("#demo-step", Static)

        if self._step_index >= len(self._steps):
            status.update("Demo status: complete")
            return

        status.update("Demo status: running...")
        await asyncio.sleep(0.2)
        progress.update(f"Step {self._step_index + 1}/{len(self._steps)}")
        step_text.update(self._steps[self._step_index])
        status.update("Demo status: success")
        self._step_index += 1
