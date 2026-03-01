"""Textual-based TUI runtime for Jikai."""

from __future__ import annotations

import asyncio
from typing import Dict

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import Screen
from textual.events import Key
from textual.widgets import Footer, Header, Label, Static

from .navigation import ROUTE_MAP
from .widgets import Breadcrumb, StatusBar


class _BaseScreen(Screen):
    """Simple base screen with a title and helper copy."""

    screen_title: str = ""
    screen_help: str = ""

    def compose(self) -> ComposeResult:
        with Container(id="screen-body"):
            yield Breadcrumb(id="breadcrumb")
            yield Label(self.screen_title, id="screen-title")
            yield Static(self.screen_help, id="screen-help")
            yield StatusBar(id="status-bar")

    def on_mount(self) -> None:
        breadcrumb = self.query_one("#breadcrumb", Breadcrumb)
        breadcrumb.set_path(f"Home > {self.screen_title}")
        status_bar = self.query_one("#status-bar", StatusBar)
        status_bar.set_states(
            corpus="ok",
            models="ok",
            embeddings="warn",
            provider="unknown",
        )


class HomeScreen(_BaseScreen):
    screen_title = ROUTE_MAP["home"].label
    screen_help = ROUTE_MAP["home"].description


class GenerateScreen(_BaseScreen):
    screen_title = ROUTE_MAP["generate"].label
    screen_help = ROUTE_MAP["generate"].description


class HistoryScreen(_BaseScreen):
    screen_title = ROUTE_MAP["history"].label
    screen_help = ROUTE_MAP["history"].description


class ProvidersScreen(_BaseScreen):
    screen_title = ROUTE_MAP["providers"].label
    screen_help = ROUTE_MAP["providers"].description
    _health_task: asyncio.Task | None = None

    async def _provider_health_loop(self) -> None:
        while True:
            provider_state = "unknown"
            try:
                from ..services.llm_service import llm_service

                health = await llm_service.health_check()
                statuses = [
                    details.get("status", "unknown")
                    for details in health.values()
                    if isinstance(details, dict)
                ]
                if statuses and all(status == "healthy" for status in statuses):
                    provider_state = "ok"
                elif any(status == "unhealthy" for status in statuses):
                    provider_state = "error"
                elif statuses:
                    provider_state = "warn"
            except Exception:
                provider_state = "warn"
            status_bar = self.query_one("#status-bar", StatusBar)
            status_bar.provider_state = provider_state
            await asyncio.sleep(10)

    def on_mount(self) -> None:
        super().on_mount()
        self._health_task = asyncio.create_task(self._provider_health_loop())

    async def on_unmount(self) -> None:
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
            self._health_task = None


class HelpScreen(_BaseScreen):
    screen_title = "Help"
    screen_help = (
        "Shortcuts: q quit, ? help, g generate, h history, p providers, home home screen."
    )


class CommandPaletteScreen(Screen):
    """Minimal modal command palette for quick route navigation."""

    def compose(self) -> ComposeResult:
        commands = [
            "1 Generate",
            "2 History",
            "3 Providers",
            "4 Home",
            "5 Help",
            "",
            "Press 1-5 to navigate, Esc to close.",
        ]
        with Container(id="screen-body"):
            yield Label("Command Palette", id="screen-title")
            yield Static("\n".join(commands), id="screen-help")

    def on_key(self, event: Key) -> None:
        if event.key == "escape":
            self.dismiss()
            return
        route_map = {
            "1": "generate",
            "2": "history",
            "3": "providers",
            "4": "home",
            "5": "help",
        }
        route = route_map.get(event.key)
        if not route:
            return
        self.dismiss()
        self.app._switch_to(route)


class JikaiTextualApp(App[None]):
    """Interactive Textual runtime with primary navigation bindings."""

    CSS = """
    #screen-body {
        padding: 1 2;
    }

    #screen-title {
        text-style: bold;
        color: cyan;
        margin-bottom: 1;
    }

    #screen-help {
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+k", "open_command_palette", "Palette"),
        Binding("question_mark", "show_help", "Help"),
        Binding("g", "show_generate", "Generate"),
        Binding("h", "show_history", "History"),
        Binding("p", "show_providers", "Providers"),
        Binding("home", "show_home", "Home"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._screens: Dict[str, Screen] = {
            "home": HomeScreen(),
            "generate": GenerateScreen(),
            "history": HistoryScreen(),
            "providers": ProvidersScreen(),
            "help": HelpScreen(),
        }

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Footer()

    def on_mount(self) -> None:
        self.push_screen(self._screens["home"])

    @on(App.PoppedScreen)
    def _on_popped_screen(self) -> None:
        if not self.screen_stack:
            self.push_screen(self._screens["home"])

    def _switch_to(self, key: str) -> None:
        self.pop_screen()
        self.push_screen(self._screens[key])

    def action_show_home(self) -> None:
        self._switch_to("home")

    def action_show_help(self) -> None:
        self._switch_to("help")

    def action_show_generate(self) -> None:
        self._switch_to("generate")

    def action_show_history(self) -> None:
        self._switch_to("history")

    def action_show_providers(self) -> None:
        self._switch_to("providers")

    def action_open_command_palette(self) -> None:
        self.push_screen(CommandPaletteScreen())
