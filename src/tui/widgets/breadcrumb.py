"""Breadcrumb widget for Textual screens."""

from __future__ import annotations

from textual.reactive import reactive
from textual.widgets import Static


class Breadcrumb(Static):
    """Simple path breadcrumb that can be updated by screens."""

    _path = reactive("Home")

    def set_path(self, path: str) -> None:
        self._path = path or "Home"

    def watch__path(self, path: str) -> None:
        self.update(f"[dim]{path}[/dim]")

    def on_mount(self) -> None:
        self.update(f"[dim]{self._path}[/dim]")
