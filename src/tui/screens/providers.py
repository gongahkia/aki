"""Providers screen for health, model selection, and defaults."""

from __future__ import annotations

import asyncio
from typing import Dict, List

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Button, DataTable, Label, Select, Static


class ProvidersScreen(Screen):
    """Manage provider availability and default provider/model selection."""

    BINDINGS = [
        Binding("r", "refresh", "Refresh"),
        Binding("escape", "close", "Close"),
    ]

    _models_by_provider: Dict[str, List[str]] = {}

    def compose(self) -> ComposeResult:
        with Container(id="screen-body"):
            yield Label("Providers", id="screen-title")
            yield DataTable(id="providers-table")
            with Horizontal():
                yield Select(options=[("Select provider", "")], value="", id="provider-select")
                yield Select(options=[("Select model", "")], value="", id="model-select")
            with Horizontal():
                yield Button("Set Default Provider", id="set-default-provider")
                yield Button("Set Default Model", id="set-default-model")
                yield Button("Run Ollama Diagnostics", id="run-ollama-diagnostics")
            yield Static("Provider status: idle", id="provider-status")
            yield Static("Ollama diagnostics: idle", id="ollama-diagnostics")
            yield Static("Press r to refresh", id="screen-help")

    def on_mount(self) -> None:
        table = self.query_one("#providers-table", DataTable)
        table.add_columns("Provider", "Health", "Models")
        asyncio.create_task(self._refresh())

    def action_close(self) -> None:
        self.dismiss()

    def action_refresh(self) -> None:
        asyncio.create_task(self._refresh())

    async def _refresh(self) -> None:
        status = self.query_one("#provider-status", Static)
        status.update("Provider status: loading...")
        try:
            from ...services.llm_service import llm_service

            health = await llm_service.health_check()
            models = await llm_service.list_models()
            self._models_by_provider = {
                provider: [m for m in model_list if isinstance(m, str)]
                for provider, model_list in models.items()
                if isinstance(model_list, list)
            }
            self._render_table(health, self._models_by_provider)
            self._rebuild_selectors()
            status.update("Provider status: loaded")
        except Exception as exc:
            status.update(f"Provider status: load failed ({exc})")

    def _render_table(self, health: Dict, models: Dict[str, List[str]]) -> None:
        table = self.query_one("#providers-table", DataTable)
        table.clear()
        for provider, state in health.items():
            healthy = False
            if isinstance(state, dict):
                healthy = bool(state.get("healthy") or state.get("status") == "healthy")
            else:
                healthy = bool(state)
            health_label = "healthy" if healthy else "unhealthy"
            model_list = models.get(provider, [])
            table.add_row(provider, health_label, ", ".join(model_list[:5]) or "-")

    def _rebuild_selectors(self) -> None:
        providers = sorted(self._models_by_provider.keys())
        provider_select = self.query_one("#provider-select", Select)
        provider_select.set_options(
            [("Select provider", "")]
            + [(provider, provider) for provider in providers]
        )
        provider_select.value = ""

        model_select = self.query_one("#model-select", Select)
        model_select.set_options([("Select model", "")])
        model_select.value = ""

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "provider-select":
            return
        provider = str(event.value or "").strip()
        model_select = self.query_one("#model-select", Select)
        if not provider:
            model_select.set_options([("Select model", "")])
            model_select.value = ""
            return
        models = self._models_by_provider.get(provider, [])
        model_select.set_options(
            [("Select model", "")]
            + [(model, model) for model in models]
        )
        model_select.value = ""

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "set-default-provider":
            asyncio.create_task(self._set_default_provider())
        elif event.button.id == "set-default-model":
            asyncio.create_task(self._set_default_model())
        elif event.button.id == "run-ollama-diagnostics":
            asyncio.create_task(self._run_ollama_diagnostics())

    async def _set_default_provider(self) -> None:
        status = self.query_one("#provider-status", Static)
        provider = str(self.query_one("#provider-select", Select).value or "").strip()
        if not provider:
            status.update("Provider status: choose a provider first")
            return
        try:
            from ...services.llm_service import llm_service

            llm_service.select_provider(provider)
            status.update(f"Provider status: default provider set to {provider}")
        except Exception as exc:
            status.update(f"Provider status: failed to set provider ({exc})")

    async def _set_default_model(self) -> None:
        status = self.query_one("#provider-status", Static)
        model = str(self.query_one("#model-select", Select).value or "").strip()
        if not model:
            status.update("Provider status: choose a model first")
            return
        try:
            from ...services.llm_service import llm_service

            llm_service.select_model(model)
            status.update(f"Provider status: default model set to {model}")
        except Exception as exc:
            status.update(f"Provider status: failed to set model ({exc})")

    async def _run_ollama_diagnostics(self) -> None:
        panel = self.query_one("#ollama-diagnostics", Static)
        panel.update("Ollama diagnostics: running...")
        host = "http://127.0.0.1:11434"
        reachable = False
        model_count = 0
        model_preview = "-"
        log_tail = "no startup log found"
        try:
            import httpx

            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"{host}/api/tags")
            if response.status_code == 200:
                reachable = True
                payload = response.json()
                models = payload.get("models", []) if isinstance(payload, dict) else []
                if isinstance(models, list):
                    names = [m.get("name", "") for m in models if isinstance(m, dict)]
                    names = [name for name in names if isinstance(name, str) and name]
                    model_count = len(names)
                    model_preview = ", ".join(names[:3]) if names else "-"
        except Exception:
            reachable = False

        try:
            from pathlib import Path

            log_path = Path("data/ollama_start.log")
            if log_path.exists():
                lines = log_path.read_text(encoding="utf-8").splitlines()
                log_tail = " | ".join(lines[-3:]) if lines else "empty log"
        except Exception:
            log_tail = "log read failed"

        panel.update(
            " | ".join(
                [
                    f"host={host}",
                    f"reachable={reachable}",
                    f"models={model_count}",
                    f"sample={model_preview}",
                    f"logs={log_tail}",
                ]
            )
        )
