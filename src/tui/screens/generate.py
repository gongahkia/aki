"""Dedicated generation form screen with inline validation."""

from __future__ import annotations

import asyncio
from typing import List

import httpx
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Select, Static

from ..services import persist_stream_generation

_VALID_COMPLEXITY = ["beginner", "basic", "intermediate", "advanced", "expert"]
_PRESETS = {
    "exam_drill": {
        "label": "Exam Drill",
        "complexity": "advanced",
        "parties": "3",
        "topics": "duty_of_care, causation, remoteness",
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
        Binding("ctrl+p", "preview", "Preview"),
        Binding("ctrl+s", "start_stream", "Stream"),
        Binding("ctrl+z", "pause_stream", "Pause"),
        Binding("ctrl+r", "resume_stream", "Resume"),
        Binding("ctrl+x", "cancel_stream", "Cancel"),
    ]
    _stream_task: asyncio.Task | None = None
    _stream_paused = False
    _stream_cancelled = False

    def compose(self) -> ComposeResult:
        with Container(id="screen-body"):
            yield Label("Generate", id="screen-title")
            yield Select(
                options=[
                    (preset["label"], key)
                    for key, preset in _PRESETS.items()
                ],
                value="exam_drill",
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
            yield Static("Preview not loaded. Press Ctrl+P.", id="preview-panel")
            yield Static("Stream state: idle", id="stream-state")
            yield Static("", id="stream-output")
            with Horizontal(id="action-dock"):
                yield Button("Report", id="action-report")
                yield Button("Regenerate", id="action-regenerate")
                yield Button("Export", id="action-export")
                yield Button("Save Preset", id="action-save-preset")
            yield Static("Action dock: idle", id="action-status")
            yield Static("Press Esc to close", id="screen-help")

    def action_close(self) -> None:
        self.dismiss()

    def action_preview(self) -> None:
        asyncio.create_task(self._load_preview())

    def action_start_stream(self) -> None:
        if self._stream_task and not self._stream_task.done():
            return
        self._stream_paused = False
        self._stream_cancelled = False
        self._stream_task = asyncio.create_task(self._run_stream())

    def action_pause_stream(self) -> None:
        if self._stream_task and not self._stream_task.done():
            self._stream_paused = True
            self.query_one("#stream-state", Static).update("Stream state: paused")

    def action_resume_stream(self) -> None:
        if self._stream_task and not self._stream_task.done():
            self._stream_paused = False
            self.query_one("#stream-state", Static).update("Stream state: streaming")

    def action_cancel_stream(self) -> None:
        self._stream_cancelled = True
        if self._stream_task and not self._stream_task.done():
            self._stream_task.cancel()
        self.query_one("#stream-state", Static).update("Stream state: cancelled")

    def on_mount(self) -> None:
        self._apply_preset("exam_drill")

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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        status = self.query_one("#action-status", Static)
        action_map = {
            "action-report": "Report",
            "action-regenerate": "Regenerate",
            "action-export": "Export",
            "action-save-preset": "Save Preset",
        }
        label = action_map.get(event.button.id or "", "Unknown")
        status.update(f"Action dock: {label} selected")

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

    async def _load_preview(self) -> None:
        panel = self.query_one("#preview-panel", Static)
        if not self._validate_all():
            panel.update("[yellow]Preview unavailable until inputs are valid.[/yellow]")
            return

        topics = self._topics()
        parties = int(self.query_one("#parties", Input).value.strip())
        complexity = str(self.query_one("#complexity", Select).value or "intermediate")
        payload = {
            "topics": topics,
            "law_domain": "tort",
            "number_parties": parties,
            "complexity_level": complexity,
            "sample_size": 3,
            "method": "pure_llm",
            "include_analysis": True,
        }

        panel.update("[dim]Loading preview...[/dim]")
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                response = await client.post(
                    "http://127.0.0.1:8000/generate/preview",
                    json=payload,
                )
            response.raise_for_status()
            data = response.json()
            panel.update(
                " | ".join(
                    [
                        f"input={data.get('estimated_input_tokens', '?')}",
                        f"output={data.get('estimated_output_tokens', '?')}",
                        f"total={data.get('estimated_total_tokens', '?')}",
                        f"latency={data.get('estimated_latency_seconds', '?')}s",
                        f"cost=${data.get('estimated_cost_usd', '?')}",
                    ]
                )
            )
        except Exception as exc:
            panel.update(f"[red]Preview failed: {exc}[/red]")

    async def _run_stream(self) -> None:
        output = self.query_one("#stream-output", Static)
        state = self.query_one("#stream-state", Static)
        if not self._validate_all():
            state.update("Stream state: blocked (invalid inputs)")
            return

        topics = self._topics()
        topic = topics[0]
        parties = int(self.query_one("#parties", Input).value.strip())
        complexity = str(self.query_one("#complexity", Select).value or "intermediate")
        complexity = complexity.lower().strip()

        state.update("Stream state: streaming")
        chunks: List[str] = []
        saved = False

        try:
            from ...services.llm_service import LLMRequest, llm_service

            request = LLMRequest(
                prompt=(
                    "Generate a Singapore tort law hypothetical about "
                    f"{topic} with {parties} parties at {complexity} complexity."
                ),
                temperature=0.7,
                stream=True,
            )
            async for chunk in llm_service.stream_generate(request):
                if self._stream_cancelled:
                    break
                while self._stream_paused and not self._stream_cancelled:
                    await asyncio.sleep(0.1)
                chunks.append(chunk)
                output.update("".join(chunks))
            if self._stream_cancelled:
                state.update("Stream state: cancelled")
            else:
                state.update("Stream state: complete")
        except asyncio.CancelledError:
            state.update("Stream state: cancelled")
        except Exception as exc:
            state.update(f"Stream state: failed ({exc})")
        finally:
            if chunks and not saved:
                complexity_score = _VALID_COMPLEXITY.index(complexity) + 1
                cancellation_metadata = (
                    {"cancelled": True, "reason": "user_interrupt"}
                    if self._stream_cancelled
                    else {}
                )
                try:
                    await persist_stream_generation(
                        topic=topic,
                        provider="ollama",
                        model=None,
                        complexity=complexity_score,
                        parties=parties,
                        method="pure_llm",
                        temperature=0.7,
                        red_herrings=False,
                        hypothetical="".join(chunks),
                        validation_results={
                            "passed": False,
                            "quality_score": 0.0,
                            "cancelled": self._stream_cancelled,
                        },
                        partial_snapshot=self._stream_cancelled,
                        cancellation_metadata=cancellation_metadata,
                        include_analysis=False,
                    )
                    saved = True
                except Exception:
                    # Non-fatal: stream result can still be shown in UI even if persistence fails.
                    pass
