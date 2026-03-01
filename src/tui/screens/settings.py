"""Settings screen for Textual runtime."""

from __future__ import annotations

import json
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Button, Label, Select, Static

from ...services.error_mapper import map_exception
_POLICY_PATH = Path("data/tui_policy.json")

_POLICY_OPTIONS = {
    "local_first": {
        "label": "Local-First",
        "order": ["ollama", "local", "openai", "anthropic", "google"],
    },
    "hybrid_balanced": {
        "label": "Hybrid",
        "order": ["ollama", "openai", "anthropic", "google", "local"],
    },
    "cloud_first": {
        "label": "Cloud-First",
        "order": ["openai", "anthropic", "google", "ollama", "local"],
    },
}


class SettingsScreen(Screen):
    """Settings editor for provider fallback policy."""

    BINDINGS = [
        Binding("escape", "close", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Container(id="screen-body"):
            yield Label("Settings", id="screen-title")
            yield Select(
                options=[(v["label"], k) for k, v in _POLICY_OPTIONS.items()],
                value="local_first",
                id="fallback-policy",
            )
            yield Static("Current fallback order: -", id="policy-order")
            yield Button("Save Policy", id="save-policy")
            yield Static("Settings status: idle", id="settings-status")

    def on_mount(self) -> None:
        self._load_policy()
        self._render_policy_order()

    def action_close(self) -> None:
        self.dismiss()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "fallback-policy":
            self._render_policy_order()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-policy":
            self._save_policy()

    def _render_policy_order(self) -> None:
        selected = str(self.query_one("#fallback-policy", Select).value or "local_first")
        policy = _POLICY_OPTIONS.get(selected, _POLICY_OPTIONS["local_first"])
        order = " -> ".join(policy["order"])
        self.query_one("#policy-order", Static).update(f"Current fallback order: {order}")

    def _load_policy(self) -> None:
        if not _POLICY_PATH.exists():
            return
        try:
            data = json.loads(_POLICY_PATH.read_text(encoding="utf-8"))
            policy = str(data.get("fallback_policy", "local_first"))
            if policy in _POLICY_OPTIONS:
                self.query_one("#fallback-policy", Select).value = policy
        except Exception as exc:
            map_exception(exc, default_status=500)
            pass

    def _save_policy(self) -> None:
        status = self.query_one("#settings-status", Static)
        selected = str(self.query_one("#fallback-policy", Select).value or "local_first")
        if selected not in _POLICY_OPTIONS:
            status.update("Settings status: invalid policy selection")
            return
        try:
            _POLICY_PATH.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "fallback_policy": selected,
                "provider_order": _POLICY_OPTIONS[selected]["order"],
            }
            _POLICY_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            status.update(f"Settings status: saved policy {selected}")
        except Exception as exc:
            mapped = map_exception(exc, default_status=500)
            status.update(f"Settings status: save failed ({mapped.message})")
